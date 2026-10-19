"""Store evaluation results as error records and (re)calculate totals with the engine.

Deduction values in the records are always written here, from config; nothing the model says is trusted as a
number. recalc_* functions are also what admin overrides call, so totals always follow the same rules.
"""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ...db import utcnow
from ...models import (AccuracyCompletenessEvaluation, AccuracyResult, AdminReview, AttemptResult, DetectionMethod,
                       DialogueAttempt, EvaluationType, FluencyError, FluencyType, LanguageQualityError,
                       LanguageQualityType, MockTestAttempt, ScoringStatus, SegmentAttempt)
from ...settings import scoring_config
from . import engine
from .evaluator import EvaluationOutcome
from .timing import TimingResult

LQ_TYPES = {"grammar": LanguageQualityType.GRAMMAR, "unidiomatic_usage": LanguageQualityType.UNIDIOMATIC_USAGE,
            "register": LanguageQualityType.REGISTER, "sentence_structure": LanguageQualityType.SENTENCE_STRUCTURE,
            "pronunciation": LanguageQualityType.PRONUNCIATION}
FL_TYPES = {"hesitation": FluencyType.HESITATION, "self_correction": FluencyType.SELF_CORRECTION,
            "Pause": FluencyType.PAUSE, "StartDelay": FluencyType.START_DELAY}
MU_RESULTS = {"correct": AccuracyResult.CORRECT, "omission": AccuracyResult.OMISSION,
              "distortion": AccuracyResult.DISTORTION}


def clear_results(db: Session, sa: SegmentAttempt) -> None:
    """Remove machine-produced results before (re)scoring. Items a teacher added by hand are kept."""
    for model in (AccuracyCompletenessEvaluation, LanguageQualityError, FluencyError):
        db.execute(delete(model).where(model.segment_attempt_id == sa.id,
                                       model.detection_method != DetectionMethod.MANUAL))
    db.expire(sa, ["accuracy_evaluations", "language_quality_errors", "fluency_errors"])


def store_unanswered(db: Session, sa: SegmentAttempt) -> None:
    """Skipped or silent answer: every Meaning Unit is an omission (config switch)."""
    clear_results(db, sa)
    if not scoring_config().get("unanswered_counts_all_meaning_units_omitted", True):
        return
    for mu in (m for m in sa.segment.meaning_units if m.active):
        db.add(AccuracyCompletenessEvaluation(
            segment_attempt_id=sa.id, evaluation_type=EvaluationType.MEANING_UNIT, meaning_unit_id=mu.id,
            result=AccuracyResult.OMISSION, source_meaning=mu.meaning, student_meaning="",
            explanation="This segment was not answered.", suggested_version=mu.reference_interpretation, confidence=1.0,
            weight=mu.weight))
    sa.ai_feedback = "This segment was not answered, so every meaning unit counts as omitted."
    db.flush()


def store_evaluation(db: Session, sa: SegmentAttempt, outcome: EvaluationOutcome, timing: TimingResult) -> None:
    cfg = scoring_config()
    clear_results(db, sa)
    ev = outcome.evaluation
    low = cfg["review"]["low_confidence_threshold"]
    mus = {m.meaning_unit_number: m for m in sa.segment.meaning_units if m.active}
    target_lang = sa.target_language_id
    for item in ev.meaning_units:
        mu = mus[item.meaning_unit]
        db.add(AccuracyCompletenessEvaluation(
            segment_attempt_id=sa.id, evaluation_type=EvaluationType.MEANING_UNIT, meaning_unit_id=mu.id,
            result=MU_RESULTS[item.result], source_meaning=mu.meaning, student_meaning=item.student_interpretation,
            explanation=item.explanation, suggested_version=item.suggested_version, confidence=item.confidence,
            weight=mu.weight))
    for ins in ev.insertions:
        db.add(AccuracyCompletenessEvaluation(
            segment_attempt_id=sa.id, evaluation_type=EvaluationType.INSERTION, result=AccuracyResult.INSERTION,
            student_meaning=ins.student_text, explanation=ins.explanation, confidence=ins.confidence))
    for lq in ev.language_quality:
        etype = LQ_TYPES[lq.error]
        db.add(LanguageQualityError(
            segment_attempt_id=sa.id, language_id=target_lang, error_type=etype, student_text=lq.student_text,
            suggested_version=lq.suggested_version, explanation=lq.explanation, confidence=lq.confidence,
            detection_method=DetectionMethod.AI,
            needs_review=etype == LanguageQualityType.PRONUNCIATION or lq.confidence < low))
    for fl in ev.fluency:
        db.add(FluencyError(
            segment_attempt_id=sa.id, language_id=target_lang, error_type=FL_TYPES[fl.error],
            transcript_excerpt=fl.transcript_excerpt, explanation=fl.explanation, confidence=fl.confidence,
            detection_method=DetectionMethod.AI))
    # Programmatic timing events (measured from the audio, not by the model).
    for e in timing.events:
        db.add(FluencyError(
            segment_attempt_id=sa.id, language_id=target_lang, error_type=FL_TYPES[e.type],
            timestamp_seconds=e.start, duration_seconds=e.duration, explanation=e.explanation, confidence=1.0,
            detection_method=DetectionMethod.AUDIO_ANALYSIS))
    sa.ai_feedback = ev.overall_feedback
    sa.scoring_confidence = ev.confidence
    sa.timing = {**(sa.timing or {}), "analysis": timing.as_dict()}
    db.flush()


def _overrides(sa: SegmentAttempt) -> dict:
    """Latest admin decision per item id."""
    out = {}
    for r in sorted(sa.admin_reviews, key=lambda r: r.created_at):
        if r.target_id:
            out[r.target_id] = r.revised_deduction
    return out


def recalc_segment(db: Session, sa: SegmentAttempt) -> engine.Totals:
    cfg = scoring_config()
    db.refresh(sa, ["accuracy_evaluations", "language_quality_errors", "fluency_errors", "admin_reviews"])
    overrides = _overrides(sa)
    rows: list = []
    items: list[engine.Item] = []
    for r in sa.accuracy_evaluations:
        rows.append(r)
        items.append(engine.Item("accuracy", r.result.value, r.weight, overrides.get(r.id)))
    for r in sa.language_quality_errors:
        rows.append(r)
        items.append(engine.Item("language", r.error_type.value, override=overrides.get(r.id)))
    for r in sa.fluency_errors:
        rows.append(r)
        items.append(engine.Item("fluency", r.error_type.value, override=overrides.get(r.id)))
    totals, results = engine.segment_totals(items, cfg)
    pending_review = False
    for row, res in zip(rows, results, strict=True):
        row.deduction = res.deduction
        if isinstance(row, LanguageQualityError):
            row.needs_review = row.needs_review and row.id not in overrides
            pending_review = pending_review or row.needs_review
    sa.accuracy_completeness_deduction = totals.accuracy
    sa.language_quality_deduction = totals.language
    sa.fluency_deduction = totals.fluency
    sa.total_deduction = totals.total
    if pending_review and not sa.reviewed_by_admin:
        sa.needs_review = True
    db.flush()
    return totals


def recalc_dialogue(db: Session, da: DialogueAttempt) -> engine.DialogueScore:
    cfg = scoring_config()
    db.refresh(da, ["segment_attempts"])
    segs = [engine.Totals(s.accuracy_completeness_deduction, s.language_quality_deduction, s.fluency_deduction)
            for s in da.segment_attempts]
    score = engine.dialogue_score(segs, da.maximum_score, da.passing_score, cfg)
    da.accuracy_completeness_deduction = score.deductions.accuracy
    da.language_quality_deduction = score.deductions.language
    da.fluency_deduction = score.deductions.fluency
    da.total_deductions = score.deductions.total
    da.total_score = score.score
    da.result = AttemptResult.PASS if score.passed else AttemptResult.FAIL
    db.flush()
    return score


def recalc_mock(db: Session, ma: MockTestAttempt) -> engine.MockScore:
    db.refresh(ma, ["dialogue_attempts"])
    dialogues = [engine.DialogueScore(engine.Totals(d.accuracy_completeness_deduction, d.language_quality_deduction,
                                                    d.fluency_deduction), d.total_score or 0, d.maximum_score,
                                      d.passing_score) for d in ma.dialogue_attempts]
    m = engine.mock_score(dialogues, ma.passing_score)
    ma.total_score, ma.maximum_score = m.total, m.maximum
    ma.result = AttemptResult.PASS if m.passed else AttemptResult.FAIL
    db.flush()
    return m


def recalc_all(db: Session, sa: SegmentAttempt) -> None:
    """After an admin change to one segment: segment -> dialogue -> mock."""
    recalc_segment(db, sa)
    da = sa.dialogue_attempt
    if da.scoring_status == ScoringStatus.COMPLETED:
        recalc_dialogue(db, da)
        if da.mock_test_attempt and da.mock_test_attempt.scoring_status == ScoringStatus.COMPLETED:
            recalc_mock(db, da.mock_test_attempt)


def add_review(db: Session, sa: SegmentAttempt, reviewer_id, target_type: str, target_id, original: float,
               revised: float, notes: str) -> AdminReview:
    review = AdminReview(segment_attempt_id=sa.id, reviewed_by=reviewer_id, target_type=target_type,
                         target_id=target_id, original_deduction=original, revised_deduction=revised,
                         review_notes=notes)
    db.add(review)
    sa.reviewed_by_admin, sa.needs_review = True, False
    sa.updated_at = utcnow()
    db.flush()
    return review
