"""Background scoring of one segment attempt (job "score_segment"), then the dialogue / mock test when every
segment is done.

    recording -> STT (words) -> timing analysis (code) -> AI evaluator (errors only) -> error records
              -> deduction engine -> segment / dialogue / mock totals -> "results ready" email
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import SessionLocal, utcnow
from ...jobs import handler, on_failure
from ...models import (AIScoringRun, DialogueAttempt, LanguageScoringConfig, LanguageType, MockTestAttempt, RunStatus,
                       ScoringStatus, SegmentAttempt)
from ...settings import get_settings, scoring_config
from ..ai.llm import LLMError, get_llm
from ..email import send_template
from ..scoring_jobs import SCORE_SEGMENT
from ..stt import STTError
from . import records
from .evaluator import PROMPT_VERSION, evaluate
from .timing import analyse
from .transcribe import cleanup, transcribe_segment

log = logging.getLogger("scoring")


class NonRetryable(RuntimeError):
    pass


def _markers(db: Session, sa: SegmentAttempt) -> tuple[list[str], LanguageScoringConfig | None]:
    cfg = db.scalar(select(LanguageScoringConfig).where(
        LanguageScoringConfig.language_id == sa.target_language_id, LanguageScoringConfig.active))
    markers = list(cfg.hesitation_markers) if cfg else []
    if sa.segment.target_language.language_type == LanguageType.ENGLISH:
        markers += scoring_config()["timing"]["english_hesitation_markers"]
    return markers, cfg


def score_one(db: Session, sa: SegmentAttempt) -> None:
    cfg = scoring_config()
    review = cfg["review"]
    if not sa.audio_user:
        records.store_unanswered(db, sa)
        return
    work = get_settings().scratch_dir / f"score-{sa.id.hex[:12]}-{uuid.uuid4().hex[:6]}"
    try:
        transcript, flac = transcribe_segment(db, sa, work)
        markers, lang_cfg = _markers(db, sa)
        timing = analyse(flac, transcript.words, transcript.text, sa.timing or {}, cfg["timing"], markers)
        if not transcript.text.strip() and not timing.speech_regions:
            records.store_unanswered(db, sa)
            sa.ai_feedback = "No speech was detected in your recording, so every meaning unit counts as omitted."
            sa.needs_review = True  # could be a microphone problem: a teacher should check
            return

        llm = get_llm()
        run = AIScoringRun(segment_attempt_id=sa.id, source_language_id=sa.source_language_id,
                           target_language_id=sa.target_language_id, kind="evaluation", provider=llm.name,
                           model=llm.model, prompt_version=PROMPT_VERSION)
        db.add(run)
        db.flush()
        try:
            outcome = evaluate(sa.segment, transcript.text, timing.filler_candidates, lang_cfg)
        except LLMError as e:
            run.status, run.error_message, run.completed_at = RunStatus.FAILED, str(e)[:2000], utcnow()
            run.raw_response = e.raw or None
            db.commit()
            raise
        run.request_data = {"system": outcome.request["system"], "user": outcome.request["user"]}
        run.raw_response = {"tries": [r.data for r in outcome.results], "provider_raw": outcome.last.raw}
        run.processed_result = outcome.evaluation.model_dump()
        run.provider, run.model = outcome.last.provider, outcome.last.model
        run.status, run.completed_at = RunStatus.SUCCESS, utcnow()
        records.store_evaluation(db, sa, outcome, timing)

        reasons = []
        if outcome.evaluation.confidence < review["low_confidence_threshold"]:
            reasons.append("low AI confidence")
        if transcript.confidence is not None and transcript.confidence < review["stt_low_confidence_threshold"]:
            reasons.append("low transcription confidence")
        if outcome.evaluation.transcript_quality == "poor":
            reasons.append("poor transcript")
        if outcome.quote_problems:
            reasons.append("quotes not found in transcript")
        if reasons:
            sa.needs_review = True
            sa.scoring_error = "Flagged for review: " + ", ".join(reasons)
    finally:
        cleanup(work)


@handler(SCORE_SEGMENT)
def score_segment_job(payload: dict) -> None:
    sa_id = uuid.UUID(payload["segment_attempt_id"])
    with SessionLocal() as db:
        sa = db.get(SegmentAttempt, sa_id)
        if not sa:
            return
        if sa.scoring_status == ScoringStatus.COMPLETED:  # retry after a later step failed: just finalize
            db.commit()
            finalize(sa_id)
            return
        sa.scoring_status, sa.scoring_error = ScoringStatus.PROCESSING, ""
        db.commit()
        try:
            score_one(db, sa)
        except (LLMError, STTError) as e:
            db.rollback()
            if not e.retryable:
                _mark_failed(db, sa_id, str(e))
                finalize(sa_id)
                return
            raise
        records.recalc_segment(db, sa)
        sa.scoring_status = ScoringStatus.COMPLETED
        db.commit()
    finalize(sa_id)


@on_failure(SCORE_SEGMENT)
def score_segment_failed(payload: dict, error: str) -> None:
    sa_id = uuid.UUID(payload["segment_attempt_id"])
    with SessionLocal() as db:
        _mark_failed(db, sa_id, error.splitlines()[0])
    finalize(sa_id)


def _mark_failed(db: Session, sa_id: uuid.UUID, error: str) -> None:
    sa = db.get(SegmentAttempt, sa_id)
    sa.scoring_status, sa.scoring_error, sa.needs_review = ScoringStatus.FAILED, error[:1000], True
    db.commit()


def finalize(segment_attempt_id: uuid.UUID) -> None:
    """When every segment of a dialogue is done, total the dialogue; when every dialogue is done, the mock test."""
    with SessionLocal() as db:
        sa = db.get(SegmentAttempt, segment_attempt_id)
        da = db.scalar(select(DialogueAttempt).where(DialogueAttempt.id == sa.dialogue_attempt_id)
                     .with_for_update(of=DialogueAttempt))
        db.refresh(da, ["segment_attempts"])
        statuses = {s.scoring_status for s in da.segment_attempts}
        if statuses & {ScoringStatus.PENDING, ScoringStatus.PROCESSING} or da.finished_at:
            db.commit()
            return
        records.recalc_dialogue(db, da)
        da.scoring_status = ScoringStatus.FAILED if ScoringStatus.FAILED in statuses else ScoringStatus.COMPLETED
        if da.scoring_status == ScoringStatus.FAILED:
            # A segment that could not be scored contributes no deductions, so any total now would be inflated.
            # Publish nothing until a teacher scores it (mark reviewed) or it is re-scored.
            da.total_score, da.result = None, None
        da.finished_at = utcnow()
        db.commit()
        if da.mock_test_attempt_id is None:
            if da.scoring_status == ScoringStatus.COMPLETED and not da.results_emailed_at:
                _results_email(db, da.user, da.dialogue.title, da.total_score, da.maximum_score, da.result, da.id)
                da.results_emailed_at = utcnow()
                db.commit()
            return
        ma = db.scalar(select(MockTestAttempt).where(MockTestAttempt.id == da.mock_test_attempt_id)
                     .with_for_update(of=MockTestAttempt))
        db.refresh(ma, ["dialogue_attempts"])
        if ma.finished_at or any(d.finished_at is None for d in ma.dialogue_attempts):
            db.commit()
            return
        failed = any(d.scoring_status == ScoringStatus.FAILED for d in ma.dialogue_attempts)
        if failed:
            ma.total_score, ma.result = None, None
        else:
            records.recalc_mock(db, ma)
        ma.scoring_status = ScoringStatus.FAILED if failed else ScoringStatus.COMPLETED
        ma.finished_at = utcnow()
        db.commit()
        if not failed and not ma.results_emailed_at:
            _results_email(db, ma.user, ma.mock_test.title, ma.total_score, ma.maximum_score, ma.result, ma.id)
            ma.results_emailed_at = utcnow()
            db.commit()


def _results_email(db: Session, user, title, total, maximum, result, attempt_id) -> None:
    send_template(db, "results_ready", user.email, {
        "first_name": user.first_name, "title": title, "total": total, "max": maximum,
        "result": result.value if result else "", "results_url": f"{get_settings().app_url}/results/{attempt_id}"},
        user_id=user.id)


def rescore_segment(db: Session, sa: SegmentAttempt) -> None:
    """Admin action: queue a fresh scoring run for one segment (previous AI results are replaced)."""
    from ...jobs import enqueue

    sa.scoring_status, sa.scoring_error = ScoringStatus.PENDING, ""
    # AI results are replaced (teacher-added items are kept), so the segment goes back to the review queue:
    # overrides made on the old AI items no longer apply.
    sa.needs_review, sa.reviewed_by_admin = True, False
    da = sa.dialogue_attempt
    da.finished_at, da.scoring_status = None, ScoringStatus.PROCESSING
    if da.mock_test_attempt:
        da.mock_test_attempt.finished_at = None
        da.mock_test_attempt.scoring_status = ScoringStatus.PROCESSING
    enqueue(db, SCORE_SEGMENT, {"segment_attempt_id": str(sa.id)}, max_attempts=4)


__all__ = ["score_segment_job", "finalize", "rescore_segment"]
