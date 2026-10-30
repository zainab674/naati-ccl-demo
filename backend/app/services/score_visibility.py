"""Per-language score gate (docs/SCORING_VALIDATION.md). A language's estimated scores (totals, criterion deductions,
per-error deductions, Pass/Fail) are shown to students only once it is listed in config/validated_languages.yaml,
which `python -m validation approve` writes after a held-out report passes the agreed bar. Until then students get the
errors found, explanations and suggested versions as practice feedback, without numbers. Staff always see everything.
"""
from pathlib import Path

import yaml

from ..settings import CONFIG_DIR

NOTICE = ("Practice feedback, score not validated. The errors below are what the AI found; we do not show an "
          "estimated score until this language's scoring has been checked against NAATI examiners' marking.")

_cache: dict[str, tuple[float, frozenset[str]]] = {}


def validated_languages() -> frozenset[str]:
    path: Path = CONFIG_DIR / "validated_languages.yaml"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    hit = _cache.get("gate")
    if hit and hit[0] == mtime:
        return hit[1]
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    codes = frozenset(((doc or {}).get("languages") or {}).keys())
    _cache["gate"] = (mtime, codes)
    return codes


def is_validated(language_code: str | None) -> bool:
    return bool(language_code) and language_code in validated_languages()


def pair_code(language_pair) -> str | None:
    return language_pair.lote.code if language_pair is not None else None


def _blank(d: dict | None) -> None:
    if d:
        for k in d:
            d[k] = None


def redact_results(payload: dict) -> dict:
    """The student results payload with every number that is, or adds up to, a score removed."""
    payload.update(total_score=None, result=None, reasons=[], score_validated=False, score_notice=NOTICE)
    _blank(payload.get("deductions"))
    for h in payload.get("history", []):
        h.update(total_score=None, result=None)
    for d in payload.get("dialogues", []):
        d.update(score=None, result=None)
        _blank(d.get("deductions"))
        for s in d.get("segments", []):
            _blank(s.get("deductions"))
            for group in ("accuracy", "insertions", "language", "fluency"):
                for item in s.get(group, []):
                    item["deduction"] = None
    return payload
