"""Results payload for the student results page and the admin review screen (admin adds raw AI output)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AIScoringRun, AttemptStatus, DialogueAttempt, MockTestAttempt, ScoringStatus, SegmentAttempt
from ..settings import ccl_config, scoring_config
from .attempts import AttemptRef


def _item_common(row, overrides: dict) -> dict:
    return {"id": str(row.id), "deduction": row.deduction, "explanation": row.explanation,
            "confidence": row.confidence, "overridden": row.id in overrides}


def segment_result(sa: SegmentAttempt, admin: bool = False) -> dict:
    show_source = admin or ccl_config().get("results", {}).get("show_source_transcript", True)
    overrides = {r.target_id: r for r in sa.admin_reviews if r.target_id}
    mus = {m.id: m for m in sa.segment.meaning_units}
    accuracy, insertions = [], []
    def order(r):
        return mus[r.meaning_unit_id].meaning_unit_number if r.meaning_unit_id else 999

    for r in sorted(sa.accuracy_evaluations, key=order):
        item = {**_item_common(r, overrides), "result": r.result.value, "source_meaning": r.source_meaning,
                "student_meaning": r.student_meaning, "suggested_version": r.suggested_version}
        if r.meaning_unit_id:
            item["meaning_unit"] = mus[r.meaning_unit_id].meaning_unit_number
            accuracy.append(item)
        else:
            insertions.append(item)
    language = [{**_item_common(r, overrides), "type": r.error_type.value, "student_text": r.student_text,
                 "suggested_version": r.suggested_version, "needs_review": r.needs_review,
                 "detection_method": r.detection_method.value} for r in sa.language_quality_errors]
    fluency = [{**_item_common(r, overrides), "type": r.error_type.value, "transcript_excerpt": r.transcript_excerpt,
                "timestamp_seconds": r.timestamp_seconds, "duration_seconds": r.duration_seconds,
                "detection_method": r.detection_method.value}
               for r in sorted(sa.fluency_errors, key=lambda r: (r.timestamp_seconds is None, r.timestamp_seconds or 0))]
    out = {
        "segment_attempt_id": str(sa.id), "number": sa.segment_number, "direction": sa.segment.direction.value,
        "source_language": sa.segment.source_language.name, "target_language": sa.segment.target_language.name,
        "source_transcript": sa.segment.transcript if show_source else None,
        "answered": bool(sa.audio_user), "skipped": sa.skipped, "has_recording": bool(sa.audio_user),
        "transcript": sa.transcript_user, "stt_provider": sa.stt_provider, "feedback": sa.ai_feedback,
        "scoring_status": sa.scoring_status.value, "needs_review": sa.needs_review, "reviewed": sa.reviewed_by_admin,
        "play_count": sa.play_count,
        "deductions": {"accuracy": sa.accuracy_completeness_deduction, "language": sa.language_quality_deduction,
                       "fluency": sa.fluency_deduction, "total": sa.total_deduction},
        "accuracy": accuracy, "insertions": insertions, "language": language, "fluency": fluency,
    }
    if admin:
        out["scoring_error"] = sa.scoring_error
        out["scoring_confidence"] = sa.scoring_confidence
        out["timing"] = sa.timing
        out["stt_words"] = sa.stt_words
        out["reviews"] = [{"id": str(r.id), "target_type": r.target_type, "target_id": str(r.target_id) if r.target_id else None,
                           "original_deduction": r.original_deduction, "revised_deduction": r.revised_deduction,
                           "notes": r.review_notes, "created_at": r.created_at.isoformat()} for r in sa.admin_reviews]
    return out


def dialogue_result(da: DialogueAttempt, admin: bool = False) -> dict:
    return {
        "dialogue_attempt_id": str(da.id), "title": da.dialogue.title, "position": da.position,
        "topic": da.dialogue.topic.name if da.dialogue.topic else None, "difficulty": da.dialogue.difficulty.value,
        "score": da.total_score, "maximum_score": da.maximum_score, "passing_score": da.passing_score,
        "result": da.result.value if da.result else None, "scoring_status": da.scoring_status.value,
        "total_repeats": da.total_repeats, "attempt_number": da.attempt_number, "dialogue_version": da.dialogue_version,
        "deductions": {"accuracy": da.accuracy_completeness_deduction, "language": da.language_quality_deduction,
                       "fluency": da.fluency_deduction, "total": da.total_deductions},
        "segments": [segment_result(sa, admin) for sa in da.segment_attempts],
    }


def attempt_results(db: Session, ref: AttemptRef, admin: bool = False) -> dict:
    cfg = scoring_config()
    das = ref.dialogue_attempts
    if ref.mock:
        total, maximum = ref.mock.total_score, ref.mock.maximum_score
        result, scoring = ref.mock.result, ref.mock.scoring_status
        title, submitted = ref.mock.mock_test.title, ref.mock.submitted_at
        history_rows = db.scalars(select(MockTestAttempt).where(
            MockTestAttempt.user_id == ref.user_id, MockTestAttempt.mock_test_id == ref.mock.mock_test_id,
            MockTestAttempt.status == AttemptStatus.COMPLETED).order_by(MockTestAttempt.submitted_at.desc())).all()
    else:
        da = das[0]
        total, maximum, result, scoring = da.total_score, da.maximum_score, da.result, da.scoring_status
        title, submitted = da.dialogue.title, da.submitted_at
        history_rows = db.scalars(select(DialogueAttempt).where(
            DialogueAttempt.user_id == ref.user_id, DialogueAttempt.dialogue_id == da.dialogue_id,
            DialogueAttempt.mock_test_attempt_id.is_(None), DialogueAttempt.status == AttemptStatus.COMPLETED)
            .order_by(DialogueAttempt.submitted_at.desc())).all()
    pending = sum(1 for d in das for s in d.segment_attempts
                  if s.scoring_status in (ScoringStatus.PENDING, ScoringStatus.PROCESSING))
    reasons = []
    if ref.mock and scoring == ScoringStatus.COMPLETED and total is not None:
        if total < cfg["pass_total"]:
            reasons.append(f"Total {total:g} is below the pass mark of {cfg['pass_total']}.")
        reasons += [f"Dialogue {d.position} scored {d.total_score:g}, below the minimum of {d.passing_score:g}."
                    for d in das if d.total_score is not None and d.total_score < d.passing_score]
    providers = {s.stt_provider for d in das for s in d.segment_attempts if s.stt_provider}
    eval_providers = set(db.scalars(select(AIScoringRun.provider).where(
        AIScoringRun.kind == "evaluation",
        AIScoringRun.segment_attempt_id.in_([s.id for d in das for s in d.segment_attempts]))))
    return {
        "id": str(ref.id), "kind": ref.kind, "title": title, "status": ref.status.value,
        "scoring_status": scoring.value, "pending_segments": pending,
        "total_score": total, "maximum_score": maximum, "result": result.value if result else None,
        "reasons": reasons, "submitted_at": submitted.isoformat() if submitted else None,
        "pass_rules": {"pass_total": cfg["pass_total"], "pass_min_per_dialogue": cfg["pass_min_per_dialogue"],
                       "dialogue_max": cfg["dialogue_max"], "total_max": cfg["total_max"]},
        "demo_scoring": "mock" in providers or "mock" in eval_providers,
        "deductions": {"accuracy": round(sum(d.accuracy_completeness_deduction for d in das), 2),
                       "language": round(sum(d.language_quality_deduction for d in das), 2),
                       "fluency": round(sum(d.fluency_deduction for d in das), 2),
                       "total": round(sum(d.total_deductions for d in das), 2)},
        "dialogues": [dialogue_result(d, admin) for d in das],
        "history": [{"id": str(h.id), "total_score": h.total_score,
                     "maximum_score": h.maximum_score, "result": h.result.value if h.result else None,
                     "submitted_at": h.submitted_at.isoformat() if h.submitted_at else None} for h in history_rows],
    }
