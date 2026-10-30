"""Label Studio setup for examiner error marking.

    python -m validation tasks fil --audio-base-url https://files.example.com/validation/fil/
        -> <data>/fil/label_studio_tasks.json   (import into a project using validation/label_studio_config.xml)
    python -m validation import-labelstudio fil export.json
        -> <data>/fil/annotations.csv            (what the evaluation harness reads)

Each task is one recorded segment answer: the student audio, the source text, and the segment's Meaning Units.
Examiners mark a time region per error (label = error type), and fill the MU number and their deduction for it;
"No errors" records that the answer was reviewed. Each examiner is a separate Label Studio user, so their marks stay
separate (completed_by), and Label Studio's own overlap settings should give every task to 2-3 examiners.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlalchemy import select

from app.models import Dialogue

from .dataset import ERROR_TYPES, Dataset

CONFIG_PATH = Path(__file__).with_name("label_studio_config.xml")
KIND_OF = {t: k for k, types in ERROR_TYPES.items() for t in types}


def tasks(db, ds: Dataset, audio_base_url: str) -> list[dict]:
    out = []
    for rec in sorted(ds.recordings.values(), key=lambda r: (r.test_id, r.dialogue_key, r.segment_no)):
        d = db.scalar(select(Dialogue).where(Dialogue.key == rec.dialogue_key))
        seg = next((s for s in (d.segments if d else []) if s.segment_number == rec.segment_no), None)
        if seg is None:
            raise LookupError(f"{rec.dialogue_key} segment {rec.segment_no} is not imported")
        mus = "\n".join(f"MU{m.meaning_unit_number}: {m.meaning}" for m in seg.meaning_units if m.active)
        name = rec.audio_path.name if rec.audio_path else ""
        out.append({"data": {
            "recording_id": rec.recording_id, "audio": audio_base_url.rstrip("/") + "/" + name,
            "direction": f"{seg.source_language.name} -> {seg.target_language.name}",
            "source_text": seg.transcript, "meaning_units": mus}})
    return out


def convert(export: list[dict], examiner_of: dict[str, str] | None = None) -> list[dict]:
    """Label Studio JSON export -> annotations.csv rows. examiner_of maps Label Studio user emails/ids to the
    examiner_id used in reports (pseudonyms such as E1, E2 keep reports free of examiner names)."""
    rows = []
    for task in export:
        rid = task["data"]["recording_id"]
        for ann in task.get("annotations", []):
            if ann.get("was_cancelled"):
                continue
            who = ann.get("completed_by")
            who = who.get("email") if isinstance(who, dict) else str(who)
            examiner = (examiner_of or {}).get(who, who)
            regions: dict[str, dict] = {}
            no_errors = False
            for r in ann.get("result", []):
                v = r.get("value", {})
                if r.get("from_name") == "no_errors" and v.get("choices"):
                    no_errors = True
                    continue
                reg = regions.setdefault(r.get("id", ""), {})
                if "labels" in v:
                    reg.update(type=v["labels"][0], start=v.get("start"), end=v.get("end"))
                elif r.get("from_name") == "mu_no":
                    reg["mu_no"] = (v.get("text") or [""])[0].strip().upper().removeprefix("MU")
                elif r.get("from_name") == "deduction":
                    reg["deduction"] = (v.get("text") or [""])[0].strip()
                elif r.get("from_name") == "quote":
                    reg["quote"] = (v.get("text") or [""])[0].strip()
            marked = [g for g in regions.values() if g.get("type")]
            if no_errors and not marked:
                rows.append({"recording_id": rid, "examiner_id": examiner, "kind": "none", "error_type": "",
                             "mu_no": "", "start_s": "", "end_s": "", "deduction": "", "quote": ""})
            for g in marked:
                t = g["type"]
                rows.append({"recording_id": rid, "examiner_id": examiner, "kind": KIND_OF.get(t, ""), "error_type": t,
                             "mu_no": g.get("mu_no", ""), "start_s": round(g["start"], 2) if g.get("start") is not None else "",
                             "end_s": round(g["end"], 2) if g.get("end") is not None else "",
                             "deduction": g.get("deduction", ""), "quote": g.get("quote", "")})
    return rows


FIELDS = ["recording_id", "examiner_id", "kind", "error_type", "mu_no", "start_s", "end_s", "deduction", "quote"]


def write_annotations(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


def load_export(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
