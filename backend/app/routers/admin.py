"""Admin overview. Every route in admin_* routers depends on require_admin."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ACTIVE_PLAN_STATUSES, require_admin
from ..models import (ContentStatus, Course, Dialogue, DialogueAttempt, EmailLog, ImportJob, SegmentAttempt, User,
                      UserRole)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731
    students = select(User.id).where(User.role == UserRole.STUDENT)
    imports = db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(5)).all()
    return {
        "students": count(students),
        "active_students": count(students.where(User.subscription_status.in_(ACTIVE_PLAN_STATUSES))),
        "dialogues_published": count(select(Dialogue.id).where(Dialogue.status == ContentStatus.PUBLISHED)),
        "dialogues_total": count(select(Dialogue.id)),
        "courses": count(select(Course.id)),
        "attempts": count(select(DialogueAttempt.id)),
        "segments_needing_review": count(select(SegmentAttempt.id).where(SegmentAttempt.needs_review,
                                                                         ~SegmentAttempt.reviewed_by_admin)),
        "emails_failed": count(select(EmailLog.id).where(EmailLog.status == "failed")),
        "recent_imports": [{"id": str(j.id), "type": j.type.value, "file_name": j.file_name, "status": j.status.value,
                            "created_at": j.created_at.isoformat()} for j in imports],
    }
