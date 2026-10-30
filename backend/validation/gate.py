"""Per-language gate: config/validated_languages.yaml lists the languages whose scores students may see, each with
the committed held-out report that earned it. `check` (run by make check / CI) fails when a listed language's report
is missing, did not pass, or was produced with a different prompt or scoring config than the one now in the repo:
changing either means the evidence no longer applies and the language must be re-validated or removed."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import yaml

from app.services.scoring.evaluator import PROMPT_VERSION
from app.settings import BASE_DIR

GATE_PATH = BASE_DIR / "config" / "validated_languages.yaml"
REPORTS_DIR = BASE_DIR.parent / "docs" / "validation" / "reports"


def read_gate() -> dict:
    doc = yaml.safe_load(GATE_PATH.read_text(encoding="utf-8")) if GATE_PATH.exists() else None
    return (doc or {}).get("languages") or {}


def current_fingerprint() -> dict:
    return {"prompt": PROMPT_VERSION,
            "scoring_yaml_sha": hashlib.sha256((BASE_DIR / "config" / "scoring.yaml").read_bytes()).hexdigest()[:12]}


def report_path(language: str) -> Path:
    return REPORTS_DIR / f"{language}-heldout.json"


def problems_for(language: str, entry: dict) -> list[str]:
    path = BASE_DIR.parent / entry.get("report", "")
    if not entry.get("report") or not path.exists():
        return [f"{language}: report {entry.get('report')!r} is not committed"]
    rep = json.loads(path.read_text(encoding="utf-8"))
    out = []
    if rep.get("split") != "heldout":
        out.append(f"{language}: the gate needs a held-out report, not '{rep.get('split')}'")
    if not rep.get("bar", {}).get("passed"):
        out.append(f"{language}: the report did not pass the bar")
    fp = current_fingerprint()
    for k, v in fp.items():
        if rep.get("run", {}).get(k) != v:
            out.append(f"{language}: validated with {k}={rep.get('run', {}).get(k)}, the repo now has {v}; re-validate")
    return out


def check() -> list[str]:
    return [p for lang, entry in read_gate().items() for p in problems_for(lang, entry or {})]


def approve(language: str, approved_by: str) -> dict:
    path = report_path(language)
    entry = {"report": str(path.relative_to(BASE_DIR.parent)).replace("\\", "/"), "approved_by": approved_by,
             "approved_at": dt.date.today().isoformat()}
    problems = problems_for(language, entry)
    if problems:
        raise RuntimeError("; ".join(problems))
    doc = yaml.safe_load(GATE_PATH.read_text(encoding="utf-8")) or {}
    doc.setdefault("languages", {})
    doc["languages"] = doc["languages"] or {}
    doc["languages"][language] = entry
    header = GATE_PATH.read_text(encoding="utf-8").split("\nlanguages:")[0]
    GATE_PATH.write_text(header + "\n" + yaml.safe_dump({"languages": doc["languages"]}, sort_keys=True), encoding="utf-8")
    return entry
