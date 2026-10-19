"""Shared CSV import helpers: parsing, a validation report, and reachability checks for URLs."""
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

MAX_CSV_BYTES = 5 * 1024 * 1024


class CsvError(ValueError):
    pass


@dataclass
class Report:
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def error(self, row: int | None, column: str, message: str) -> None:
        self.errors.append({"row": row, "column": column, "message": message})

    def warn(self, row: int | None, column: str, message: str) -> None:
        self.warnings.append({"row": row, "column": column, "message": message})

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        # Cap the stored lists; a broken file can produce thousands of identical errors.
        return {"ok": self.ok, "error_count": len(self.errors), "warning_count": len(self.warnings),
                "errors": self.errors[:500], "warnings": self.warnings[:500], "summary": self.summary}


def read_csv(data: bytes, required: list[str], optional: list[str]) -> list[dict]:
    """Returns rows as dicts with stripped values and a "_row" (spreadsheet row number, header = 1)."""
    if len(data) > MAX_CSV_BYTES:
        raise CsvError(f"File is larger than {MAX_CSV_BYTES // (1024 * 1024)} MB")
    try:
        text = data.decode("utf-8-sig")  # Excel adds a BOM
    except UnicodeDecodeError as e:
        raise CsvError("File is not UTF-8. In Excel use 'Save as > CSV UTF-8'.") from e
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvError("File is empty")
    headers = [h.strip().lower() for h in reader.fieldnames]
    missing = [c for c in required if c not in headers]
    if missing:
        raise CsvError(f"Missing column(s): {', '.join(missing)}")
    unknown = [h for h in headers if h and h not in required + optional]
    rows = []
    for i, raw in enumerate(reader, start=2):
        row = {h: (v or "").strip() for h, v in zip(headers, [raw.get(k) for k in reader.fieldnames], strict=True)}
        if not any(row.values()):
            continue  # blank line
        row["_row"] = i
        rows.append(row)
    if not rows:
        raise CsvError("File has a header row but no data rows")
    if unknown:
        rows[0]["_unknown_columns"] = unknown
    return rows


def parse_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in ("", "0", "false", "no", "n"):
        return False if v else None
    if v in ("1", "true", "yes", "y"):
        return True
    raise ValueError(value)


def valid_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("https", "http") and bool(p.netloc)


def check_url(url: str, timeout: float = 10.0) -> str | None:
    """None when the URL answers 2xx; otherwise a short reason. Falls back to a 1-byte GET when HEAD is refused."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as c:
            r = c.head(url)
            if r.status_code in (403, 405, 501) or r.status_code >= 400:
                r = c.get(url, headers={"Range": "bytes=0-0"})
            if r.status_code < 400:
                return None
            return f"HTTP {r.status_code}"
    except httpx.HTTPError as e:
        return type(e).__name__


def check_urls(urls: set[str], workers: int = 8) -> dict[str, str | None]:
    urls = sorted(urls)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(urls, pool.map(check_url, urls), strict=True))
