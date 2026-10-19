"""Compare AI scoring with teacher marking on real answers (the 10-sample test with Benchmark).

    python -m scripts.eval_against_teacher samples.csv [--out report.csv]

samples.csv columns (one row per recorded segment answer; see scripts/teacher_samples_template.csv):
    sample_id, dialogue_key, segment_no, audio_path, teacher_accuracy, teacher_language, teacher_fluency
    optional: transcript (skip speech-to-text and use this text), notes

The dialogue must already be imported (its Meaning Units are what the AI checks). Each answer goes through the same
steps as production scoring - STT, timing analysis, AI evaluator, deduction engine - but nothing is written to the
database. Uses whatever STT/evaluator providers are configured in .env (mock if no keys).
"""
import argparse
import csv
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Dialogue, LanguageScoringConfig, LanguageType, Segment
from app.services.scoring import engine
from app.services.scoring.evaluator import evaluate
from app.services.scoring.timing import analyse
from app.services.stt import get_stt, normalise_audio
from app.settings import scoring_config

CRITERIA = ("accuracy", "language", "fluency")
AI_LQ = {"grammar": "Grammar", "unidiomatic_usage": "UnidiomaticUsage", "register": "Register",
         "sentence_structure": "SentenceStructure", "pronunciation": "Pronunciation"}
AI_FL = {"hesitation": "Hesitation", "self_correction": "SelfCorrection"}


@dataclass
class SampleResult:
    sample_id: str
    ai: engine.Totals
    teacher: engine.Totals
    transcript: str
    detail: str


def load_segment(db, dialogue_key: str, segment_no: int) -> Segment:
    d = db.scalar(select(Dialogue).where(Dialogue.key == dialogue_key))
    if not d:
        raise SystemExit(f"Dialogue {dialogue_key!r} is not imported")
    seg = next((s for s in d.segments if s.segment_number == segment_no and s.active), None)
    if not seg:
        raise SystemExit(f"{dialogue_key} has no active segment {segment_no}")
    return seg


def score_answer(db, seg: Segment, audio: Path | None, transcript_text: str | None) -> tuple[engine.Totals, str, str]:
    cfg = scoring_config()
    lang_cfg = db.scalar(select(LanguageScoringConfig).where(LanguageScoringConfig.language_id == seg.target_language_id,
                                                             LanguageScoringConfig.active))
    markers = list(lang_cfg.hesitation_markers) if lang_cfg else []
    if seg.target_language.language_type == LanguageType.ENGLISH:
        markers += cfg["timing"]["english_hesitation_markers"]
    with tempfile.TemporaryDirectory() as tmp:
        flac, words = None, []
        if audio is not None:
            flac = normalise_audio(audio, Path(tmp) / "a.flac")
        if transcript_text is None:
            if flac is None:
                raise SystemExit("Each sample needs an audio_path or a transcript")
            t = get_stt().transcribe(flac, seg.target_language.stt_code or None)
            transcript_text, words = t.text, t.words
        timing = analyse(flac, words, transcript_text, {}, cfg["timing"], markers)
        outcome = evaluate(seg, transcript_text, timing.filler_candidates, lang_cfg)
    ev = outcome.evaluation
    weights = {m.meaning_unit_number: m.weight for m in seg.meaning_units if m.active}
    items = [engine.Item("accuracy", m.result.capitalize(), weights.get(m.meaning_unit, 1.0)) for m in ev.meaning_units]
    items += [engine.Item("accuracy", "Insertion") for _ in ev.insertions]
    items += [engine.Item("language", AI_LQ[e.error]) for e in ev.language_quality]
    items += [engine.Item("fluency", AI_FL[e.error]) for e in ev.fluency]
    items += [engine.Item("fluency", e.type) for e in timing.events]
    totals, _ = engine.segment_totals(items, cfg)
    detail = "; ".join(
        [f"MU{m.meaning_unit} {m.result}" for m in ev.meaning_units if m.result != "correct"]
        + [f"insertion '{i.student_text}'" for i in ev.insertions]
        + [f"{e.error} '{e.student_text}'" for e in ev.language_quality]
        + [f"{e.error}" for e in ev.fluency] + [e.type for e in timing.events])
    return totals, transcript_text, detail


def run(manifest: Path) -> list[SampleResult]:
    rows = list(csv.DictReader(manifest.read_text(encoding="utf-8-sig").splitlines()))
    results = []
    with SessionLocal() as db:
        for row in rows:
            seg = load_segment(db, row["dialogue_key"].strip(), int(row["segment_no"]))
            audio = None
            if row.get("audio_path", "").strip():
                audio = Path(row["audio_path"].strip())
                if not audio.is_absolute():
                    audio = manifest.parent / audio
            transcript = row.get("transcript", "").strip() or None
            ai, text, detail = score_answer(db, seg, audio, transcript)
            teacher = engine.Totals(float(row["teacher_accuracy"] or 0), float(row["teacher_language"] or 0),
                                    float(row["teacher_fluency"] or 0))
            results.append(SampleResult(row["sample_id"], ai, teacher, text, detail))
            print(f"  scored {row['sample_id']}", file=sys.stderr)
    return results


def summary(results: list[SampleResult]) -> dict:
    out = {}
    n = len(results) or 1
    for c in (*CRITERIA, "total"):
        diffs = [getattr(r.ai, c) - getattr(r.teacher, c) for r in results]
        out[c] = {"mean_abs_diff": round(sum(abs(d) for d in diffs) / n, 2), "mean_diff": round(sum(diffs) / n, 2),
                  "exact": sum(1 for d in diffs if abs(d) < 1e-9), "within_0_5": sum(1 for d in diffs if abs(d) <= 0.5 + 1e-9)}
    return out


def print_report(results: list[SampleResult]) -> None:
    head = f"{'sample':<14}" + "".join(f"{c[:8]:>10} AI/T" for c in (*CRITERIA, "total"))
    print(head)
    print("-" * len(head))
    for r in results:
        cells = "".join(f"{getattr(r.ai, c):>9g}/{getattr(r.teacher, c):<5g}" for c in (*CRITERIA, "total"))
        print(f"{r.sample_id:<14}{cells}")
    print()
    for c, s in summary(results).items():
        print(f"{c:<9} mean |AI - teacher| = {s['mean_abs_diff']:<5g} bias = {s['mean_diff']:+g}  "
              f"exact {s['exact']}/{len(results)}  within 0.5: {s['within_0_5']}/{len(results)}")
    print("\nPositive bias = the AI deducts more than the teacher.")


def write_csv(results: list[SampleResult], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", *[f"ai_{c}" for c in CRITERIA], "ai_total", *[f"teacher_{c}" for c in CRITERIA],
                    "teacher_total", "transcript", "ai_errors"])
        for r in results:
            w.writerow([r.sample_id, *[getattr(r.ai, c) for c in CRITERIA], r.ai.total,
                        *[getattr(r.teacher, c) for c in CRITERIA], r.teacher.total, r.transcript, r.detail])


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("manifest", type=Path)
    p.add_argument("--out", type=Path, help="write a per-sample CSV report")
    args = p.parse_args(argv)
    results = run(args.manifest)
    print_report(results)
    if args.out:
        write_csv(results, args.out)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
