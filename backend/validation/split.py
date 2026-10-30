"""Development / held-out split, frozen once, and a ledger of every held-out run.

The split is by student, never by segment: answers from one student must not be on both sides, or the held-out score
would be inflated by tuning on that student's other answers. Assignment is a hash of the student id with a salt fixed
at freeze time, so it does not depend on file order. split.json records the held-out recording ids and their sha256;
any change to the held-out set afterwards is detected and refused.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets

from .ai_runs import git_commit
from .dataset import Dataset

DEFAULT_HELD_OUT_SHARE = 0.4


class SplitError(RuntimeError):
    pass


def _digest(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def freeze(ds: Dataset, share: float = DEFAULT_HELD_OUT_SHARE) -> dict:
    path = ds.root / "split.json"
    if path.exists():
        raise SplitError(f"{path} already exists. The split is frozen; delete it only to start a new study, and say so "
                         "in docs/SCORING_VALIDATION.md.")
    salt = secrets.token_hex(8)
    held_students = sorted({r.student_id for r in ds.recordings.values()
                            if int(hashlib.sha256(f"{salt}:{r.student_id}".encode()).hexdigest(), 16) % 1000 < share * 1000})
    held = sorted(r.recording_id for r in ds.recordings.values() if r.student_id in held_students)
    doc = {"created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "commit": git_commit(), "salt": salt,
           "held_out_share": share, "held_out_students": held_students, "held_out_recordings": held,
           "held_out_sha256": _digest(held)}
    path.write_text(json.dumps(doc, indent=1))
    return doc


def load(ds: Dataset) -> dict:
    path = ds.root / "split.json"
    if not path.exists():
        raise SplitError(f"No frozen split for '{ds.language}'. Run: python -m validation freeze {ds.language}")
    doc = json.loads(path.read_text())
    if _digest(doc["held_out_recordings"]) != doc["held_out_sha256"]:
        raise SplitError("split.json was edited after it was frozen (held-out checksum does not match)")
    return doc


def recordings_for(ds: Dataset, split: str) -> list[str]:
    doc = load(ds)
    held = set(doc["held_out_recordings"])
    new_students = {r.student_id for r in ds.recordings.values() if r.recording_id not in held} & set(
        doc["held_out_students"])
    if new_students:
        raise SplitError(f"New recordings from held-out students {sorted(new_students)} appeared after freezing; they "
                         "would leak. Keep them out of the dataset or start a new study.")
    if split == "heldout":
        return sorted(rid for rid in ds.recordings if rid in held)
    return sorted(rid for rid in ds.recordings if rid not in held)


def log_heldout_run(ds: Dataset, reason: str, run: dict, bar: dict) -> int:
    """Appends to heldout_runs.jsonl and returns how many held-out runs there have been. More than one means the
    held-out set influenced a later change; the report must say so."""
    path = ds.root / "heldout_runs.jsonl"
    entry = {"at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "reason": reason, "run": run,
             "bar_passed": bar["passed"]}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return sum(1 for _ in path.open(encoding="utf-8"))
