"""The validation dataset: files supplied by Benchmark (recordings, examiner marks, human transcripts and timings,
real exam results), read from VALIDATION_DATA_DIR/<language>/. Student audio and marks are personal data: they live
outside the repository (backend/data/ is gitignored) and only aggregate reports are committed.

Layout of <data>/<language>/ (formats in docs/validation/ANNOTATION_GUIDE.md):
    recordings.csv     recording_id, student_id, test_id, dialogue_key, segment_no, audio_path, consent[, notes]
    annotations.csv    recording_id, examiner_id, kind, error_type, mu_no, start_s, end_s, deduction, quote[, note]
    dialogue_marks.csv test_id, dialogue_key, examiner_id, score          (optional: examiners' own dialogue marks)
    transcripts.csv    recording_id, transcript, mixed_language           (optional: human transcripts)
    timings.csv        recording_id, speech_start_s, pauses               (optional: hand-marked; pauses "3.1-6.4;...")
    exam_results.csv   student_id, exam_date, total, dialogue_1, dialogue_2, result   (optional: real NAATI results)
    split.json         written by `python -m validation freeze`, never edited by hand
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .metrics import MU_TYPES, ErrorItem

ERROR_TYPES = {
    "accuracy": {"omission", "distortion", "insertion"},
    "language": {"grammar", "unidiomatic_usage", "register", "sentence_structure", "pronunciation",
                 "indirect_speech", "other_language"},
    "fluency": {"pause", "start_delay", "hesitation", "self_correction"},
}
# Kinds the platform's evaluator cannot report at all today. Examiners still mark them, so the report shows the gap.
NOT_DETECTED_BY_AI = {"indirect_speech", "other_language"}


class DatasetError(ValueError):
    pass


def data_root() -> Path:
    from app.settings import BASE_DIR
    return Path(os.environ.get("VALIDATION_DATA_DIR") or BASE_DIR / "data" / "validation")


def _read(path: Path, required: list[str], optional: bool = False) -> list[dict]:
    if not path.exists():
        if optional:
            return []
        raise DatasetError(f"Missing {path.name} in {path.parent}")
    rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    missing = [c for c in required if rows and c not in rows[0]]
    if missing:
        raise DatasetError(f"{path.name}: missing column(s) {', '.join(missing)}")
    return [{k: (v or "").strip() for k, v in r.items()} for r in rows]


def _float(v: str) -> float | None:
    return float(v) if v not in ("", None) else None


@dataclass
class Recording:
    recording_id: str
    student_id: str
    test_id: str
    dialogue_key: str
    segment_no: int
    audio_path: Path | None


@dataclass
class Annotation:
    examiner_id: str
    item: ErrorItem | None          # None: the examiner reviewed the recording and found no errors
    criterion: str = ""
    deduction: float | None = None  # the examiner's own deduction (NAATI deducts by impact on communication)
    quote: str = ""


@dataclass
class Dataset:
    language: str
    root: Path
    recordings: dict[str, Recording]
    annotations: dict[str, list[Annotation]]                 # recording_id -> marks from every examiner
    dialogue_marks: dict[tuple[str, str], dict[str, float]]  # (test_id, dialogue_key) -> examiner -> score
    transcripts: dict[str, tuple[str, bool]]                 # recording_id -> (text, mixed language)
    timings: dict[str, tuple[float | None, list[tuple[float, float]]]]
    exam_results: dict[str, dict]
    problems: list[str] = field(default_factory=list)

    def examiners(self) -> list[str]:
        return sorted({a.examiner_id for marks in self.annotations.values() for a in marks})

    def reviewed_by(self, recording_id: str) -> set[str]:
        return {a.examiner_id for a in self.annotations.get(recording_id, [])}

    def errors(self, recording_id: str, examiner: str) -> list[ErrorItem]:
        return [a.item for a in self.annotations.get(recording_id, []) if a.examiner_id == examiner and a.item]

    def dialogue_units(self) -> dict[tuple[str, str], list[str]]:
        """(test_id, dialogue_key) -> its recording ids in segment order."""
        out: dict[tuple[str, str], list[Recording]] = defaultdict(list)
        for r in self.recordings.values():
            out[(r.test_id, r.dialogue_key)].append(r)
        return {k: [r.recording_id for r in sorted(v, key=lambda r: r.segment_no)] for k, v in out.items()}

    def student_of_unit(self, unit: tuple[str, str]) -> str:
        rid = self.dialogue_units()[unit][0]
        return self.recordings[rid].student_id


def load(language: str, root: Path | None = None) -> Dataset:
    base = (root or data_root()) / language
    if not base.is_dir():
        raise DatasetError(f"No validation data for '{language}' at {base}. See docs/validation/ANNOTATION_GUIDE.md.")
    problems: list[str] = []
    recordings = {}
    for r in _read(base / "recordings.csv", ["recording_id", "student_id", "test_id", "dialogue_key", "segment_no",
                                             "audio_path", "consent"]):
        if r["consent"].lower() not in ("yes", "y", "true"):
            problems.append(f"{r['recording_id']}: no consent recorded, excluded")
            continue
        audio = Path(r["audio_path"]) if r["audio_path"] else None
        if audio and not audio.is_absolute():
            audio = base / audio
        recordings[r["recording_id"]] = Recording(r["recording_id"], r["student_id"], r["test_id"], r["dialogue_key"],
                                                  int(r["segment_no"]), audio)

    annotations: dict[str, list[Annotation]] = defaultdict(list)
    for i, a in enumerate(_read(base / "annotations.csv", ["recording_id", "examiner_id", "kind", "error_type",
                                                          "mu_no", "start_s", "end_s", "deduction", "quote"]), 2):
        rid, kind, etype = a["recording_id"], a["kind"].lower(), a["error_type"].lower()
        if rid not in recordings:
            problems.append(f"annotations.csv row {i}: unknown or excluded recording {rid}")
            continue
        if kind == "none":
            annotations[rid].append(Annotation(a["examiner_id"], None))
            continue
        if kind not in ERROR_TYPES or etype not in ERROR_TYPES[kind]:
            problems.append(f"annotations.csv row {i}: unknown {kind}/{etype}")
            continue
        mu = int(a["mu_no"]) if a["mu_no"] else None
        if etype in MU_TYPES and mu is None:
            problems.append(f"annotations.csv row {i}: {etype} needs mu_no")
            continue
        annotations[rid].append(Annotation(
            a["examiner_id"], ErrorItem(rid, etype, mu, _float(a["start_s"]), _float(a["end_s"])), kind,
            _float(a["deduction"]), a["quote"]))

    marks: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for m in _read(base / "dialogue_marks.csv", ["test_id", "dialogue_key", "examiner_id", "score"], optional=True):
        marks[(m["test_id"], m["dialogue_key"])][m["examiner_id"]] = float(m["score"])

    transcripts = {t["recording_id"]: (t["transcript"], t.get("mixed_language", "").lower() in ("yes", "y", "true"))
                   for t in _read(base / "transcripts.csv", ["recording_id", "transcript"], optional=True)}

    timings = {}
    for t in _read(base / "timings.csv", ["recording_id", "speech_start_s", "pauses"], optional=True):
        pauses = []
        for part in filter(None, t["pauses"].split(";")):
            a, b = part.split("-")
            pauses.append((float(a), float(b)))
        timings[t["recording_id"]] = (_float(t["speech_start_s"]), pauses)

    exams = {e["student_id"]: e for e in _read(base / "exam_results.csv",
                                               ["student_id", "exam_date", "total", "dialogue_1", "dialogue_2", "result"],
                                               optional=True)}
    unreviewed = [rid for rid in recordings if not annotations.get(rid)]
    if unreviewed:
        problems.append(f"{len(unreviewed)} recording(s) have no examiner marks (not even kind=none)")
    return Dataset(language, base, recordings, dict(annotations), dict(marks), transcripts, timings, exams, problems)
