"""Admin: students, review queue, attempt review with overrides (AdminReview) and recalculation."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_admin
from ..models import (AccuracyCompletenessEvaluation, AccuracyResult, AIScoringRun, DetectionMethod, DialogueAttempt,
                      EvaluationType, FluencyError, FluencyType, LanguageQualityError, LanguageQualityType,
                      LessonProgress, Payment, ScoringStatus, SegmentAttempt, Subscription,
                      SubscriptionStatus, User, UserRole)
from ..services import attempts as svc
from ..services.results import attempt_results, segment_result
from ..services.scoring import records
from ..services.scoring.pipeline import finalize, rescore_segment
from .student import _my_attempts, attempt_summary

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ------------------------------------------------------------------ students

@router.get("/students")
def students(q: str = "", status: str = "", db: Session = Depends(get_db)):
    query = select(User).where(User.role == UserRole.STUDENT).order_by(User.created_at.desc())
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(User.email).like(like), func.lower(User.first_name).like(like),
                                func.lower(User.last_name).like(like)))
    if status:
        query = query.where(User.subscription_status == SubscriptionStatus(status))
    rows = db.scalars(query.limit(500)).all()
    ids = [u.id for u in rows]
    stats = {uid: (n, avg, last) for uid, n, avg, last in db.execute(
        select(DialogueAttempt.user_id, func.count(), func.avg(DialogueAttempt.total_score),
               func.max(DialogueAttempt.started_at)).where(DialogueAttempt.user_id.in_(ids))
        .group_by(DialogueAttempt.user_id))}
    out = []
    for u in rows:
        n, avg, last = stats.get(u.id, (0, None, None))
        out.append({"id": str(u.id), "name": u.full_name, "email": u.email, "subscription_status": u.subscription_status.value,
                    "created_at": u.created_at.isoformat(), "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                    "dialogue_attempts": n, "average_dialogue_score": round(float(avg), 1) if avg is not None else None,
                    "last_attempt_at": last.isoformat() if last else None, "flagged": u.flagged})
    return out


@router.get("/students/{user_id}")
def student(user_id: uuid.UUID, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Student not found")
    subs = db.scalars(select(Subscription).where(Subscription.user_id == u.id).order_by(Subscription.created_at.desc())).all()
    payments = db.scalars(select(Payment).where(Payment.user_id == u.id).order_by(Payment.created_at.desc())).all()
    return {
        "id": str(u.id), "name": u.full_name, "email": u.email, "role": u.role.value,
        "subscription_status": u.subscription_status.value, "stripe_customer_id": u.stripe_customer_id,
        "target_exam_date": u.target_exam_date.isoformat() if u.target_exam_date else None,
        "created_at": u.created_at.isoformat(), "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "flagged": u.flagged,
        "lessons_completed": db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.user_id == u.id)),
        "subscriptions": [{"plan": s.plan.name if s.plan else None, "status": s.status, "stripe_subscription_id": s.stripe_subscription_id,
                           "current_period_end": s.current_period_end.isoformat() if s.current_period_end else None,
                           "cancel_at_period_end": s.cancel_at_period_end} for s in subs],
        "payments": [{"amount": p.amount, "currency": p.currency, "status": p.status, "receipt_url": p.receipt_url,
                      "created_at": p.created_at.isoformat()} for p in payments],
        "attempts": [attempt_summary(db, r) for r in _my_attempts(db, u.id)],
    }


# ------------------------------------------------------------------ review queue and attempt detail

def _attempt_id_for(sa: SegmentAttempt) -> uuid.UUID:
    da = sa.dialogue_attempt
    return da.mock_test_attempt_id or da.id


@router.get("/review-queue")
def review_queue(db: Session = Depends(get_db)):
    rows = db.scalars(select(SegmentAttempt).where(
        or_(SegmentAttempt.needs_review, SegmentAttempt.scoring_status == ScoringStatus.FAILED),
        ~SegmentAttempt.reviewed_by_admin).order_by(SegmentAttempt.submitted_at).limit(200)).all()
    return [{"segment_attempt_id": str(sa.id), "attempt_id": str(_attempt_id_for(sa)),
             "student": sa.dialogue_attempt.user.full_name, "dialogue": sa.dialogue_attempt.dialogue.title,
             "segment_number": sa.segment_number, "scoring_status": sa.scoring_status.value,
             "reason": sa.scoring_error or ("Pronunciation flagged" if any(e.needs_review for e in sa.language_quality_errors)
                                            else "Needs review"),
             "submitted_at": sa.submitted_at.isoformat() if sa.submitted_at else None} for sa in rows]


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: uuid.UUID, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    ref = svc.resolve(db, attempt_id, cu.user, allow_admin=True)
    owner = db.get(User, ref.user_id)
    data = attempt_results(db, ref, admin=True) if ref.status.value != "In Progress" else {
        "id": str(ref.id), "kind": ref.kind, "status": ref.status.value, "dialogues": []}
    data["student"] = {"id": str(owner.id), "name": owner.full_name, "email": owner.email,
                       "subscription_status": owner.subscription_status.value, "flagged": owner.flagged}
    data["integrity_events"] = [e for da in ref.dialogue_attempts for e in (da.integrity_events or [])]
    return data


@router.get("/segment-attempts/{sa_id}/runs")
def runs(sa_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = db.scalars(select(AIScoringRun).where(AIScoringRun.segment_attempt_id == sa_id).order_by(AIScoringRun.created_at)).all()
    return [{"id": str(r.id), "kind": r.kind, "provider": r.provider, "model": r.model, "prompt_version": r.prompt_version,
             "status": r.status.value, "error_message": r.error_message, "request_data": r.request_data,
             "raw_response": r.raw_response, "processed_result": r.processed_result,
             "created_at": r.created_at.isoformat(), "completed_at": r.completed_at.isoformat() if r.completed_at else None}
            for r in rows]


def _segment_or_404(db: Session, sa_id: uuid.UUID) -> SegmentAttempt:
    sa = db.get(SegmentAttempt, sa_id)
    if not sa:
        raise HTTPException(404, "Segment attempt not found")
    return sa


ITEM_MODELS = {"accuracy": AccuracyCompletenessEvaluation, "language": LanguageQualityError, "fluency": FluencyError}


class OverrideIn(BaseModel):
    target_type: str = Field(pattern="^(accuracy|language|fluency)$")
    target_id: uuid.UUID
    revised_deduction: float = Field(ge=0, le=10)
    notes: str = Field(min_length=3, max_length=2000)


@router.post("/segment-attempts/{sa_id}/override")
def override(sa_id: uuid.UUID, body: OverrideIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    sa = _segment_or_404(db, sa_id)
    item = db.get(ITEM_MODELS[body.target_type], body.target_id)
    if not item or item.segment_attempt_id != sa.id:
        raise HTTPException(404, "Item not found in this segment")
    records.add_review(db, sa, cu.id, body.target_type, item.id, item.deduction, body.revised_deduction, body.notes.strip())
    records.recalc_all(db, sa)
    db.commit()
    return segment_result(sa, admin=True)


class ManualItemIn(BaseModel):
    criterion: str = Field(pattern="^(insertion|language|fluency)$")
    type: str = ""
    student_text: str = ""
    suggested_version: str = ""
    explanation: str = Field(min_length=3, max_length=2000)
    notes: str = Field(default="", max_length=2000)


@router.post("/segment-attempts/{sa_id}/items")
def add_item(sa_id: uuid.UUID, body: ManualItemIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """A teacher adds an error the AI missed. Its deduction comes from config like any other item."""
    sa = _segment_or_404(db, sa_id)
    try:
        if body.criterion == "insertion":
            row = AccuracyCompletenessEvaluation(segment_attempt_id=sa.id, evaluation_type=EvaluationType.INSERTION,
                                                 result=AccuracyResult.INSERTION, student_meaning=body.student_text,
                                                 explanation=body.explanation, confidence=1.0)
        elif body.criterion == "language":
            row = LanguageQualityError(segment_attempt_id=sa.id, language_id=sa.target_language_id,
                                       error_type=LanguageQualityType(body.type), student_text=body.student_text,
                                       suggested_version=body.suggested_version, explanation=body.explanation,
                                       detection_method=DetectionMethod.MANUAL, confidence=1.0)
        else:
            row = FluencyError(segment_attempt_id=sa.id, language_id=sa.target_language_id, error_type=FluencyType(body.type),
                               transcript_excerpt=body.student_text, explanation=body.explanation,
                               detection_method=DetectionMethod.MANUAL, confidence=1.0)
    except ValueError as e:
        raise HTTPException(400, f"Unknown type {body.type!r}") from e
    db.add(row)
    db.flush()
    records.add_review(db, sa, cu.id, body.criterion if body.criterion != "insertion" else "accuracy", None, 0, 0,
                       body.notes or f"Added {body.criterion} item: {body.explanation}")
    records.recalc_all(db, sa)
    db.commit()
    return segment_result(sa, admin=True)


class ReviewedIn(BaseModel):
    notes: str = Field(default="", max_length=2000)


@router.post("/segment-attempts/{sa_id}/reviewed")
def mark_reviewed(sa_id: uuid.UUID, body: ReviewedIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    sa = _segment_or_404(db, sa_id)
    records.add_review(db, sa, cu.id, "segment", None, sa.total_deduction, sa.total_deduction, body.notes or "Reviewed")
    for e in sa.language_quality_errors:
        e.needs_review = False
    if sa.scoring_status == ScoringStatus.FAILED:
        # The teacher has scored this segment by hand (items added/overridden): count it as scored and re-total.
        sa.scoring_status = ScoringStatus.COMPLETED
        records.recalc_segment(db, sa)
        sa.dialogue_attempt.finished_at = None
        if sa.dialogue_attempt.mock_test_attempt:
            sa.dialogue_attempt.mock_test_attempt.finished_at = None
        db.commit()
        finalize(sa.id)
        db.refresh(sa)
        return segment_result(sa, admin=True)
    records.recalc_all(db, sa)
    db.commit()
    return segment_result(sa, admin=True)


@router.post("/segment-attempts/{sa_id}/rescore")
def rescore(sa_id: uuid.UUID, db: Session = Depends(get_db)):
    sa = _segment_or_404(db, sa_id)
    if sa.dialogue_attempt.status.value == "In Progress":
        raise HTTPException(409, "The attempt has not been submitted")
    rescore_segment(db, sa)
    db.commit()
    return {"ok": True}
