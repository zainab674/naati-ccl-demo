"""Admin overview and teacher class links (admins and teachers). Content, import and settings routers require_admin;
the student, enrolment, review and course routers require_staff and limit teachers to their own (services/teachers)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ACTIVE_PLAN_STATUSES, CurrentUser, require_admin, require_staff
from ..models import (ContentStatus, Course, Dialogue, DialogueAttempt, EmailLog, ImportJob, SegmentAttempt, User,
                      UserRole)
from ..services import teachers
from ..settings import get_settings

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_staff)])


@router.get("/overview")
def overview(cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """Admins see the whole platform; a teacher's student, attempt, review and course counts are their own."""
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731
    me = cu.user
    students = teachers.scope_students(select(User.id).where(User.role == UserRole.STUDENT), me)
    attempts = teachers.scope_by_student(select(DialogueAttempt.id), me, DialogueAttempt.user_id)
    review = teachers.scope_by_student(
        select(SegmentAttempt.id).join(DialogueAttempt, SegmentAttempt.dialogue_attempt_id == DialogueAttempt.id)
        .where(SegmentAttempt.needs_review, ~SegmentAttempt.reviewed_by_admin), me, DialogueAttempt.user_id)
    courses = select(Course.id) if me.is_admin else select(Course.id).where(Course.owner_id == me.id)
    imports = db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(5)).all() if me.is_admin else []
    return {
        "students": count(students),
        "active_students": count(students.where(User.subscription_status.in_(ACTIVE_PLAN_STATUSES))),
        "dialogues_published": count(select(Dialogue.id).where(Dialogue.status == ContentStatus.PUBLISHED)),
        "dialogues_total": count(select(Dialogue.id)),
        "courses": count(courses),
        "attempts": count(attempts),
        "segments_needing_review": count(review),
        "emails_failed": count(select(EmailLog.id).where(EmailLog.status == "failed")) if me.is_admin else 0,
        "recent_imports": [{"id": str(j.id), "type": j.type.value, "file_name": j.file_name, "status": j.status.value,
                            "created_at": j.created_at.isoformat()} for j in imports],
    }


@router.get("/join-link")
def join_link(cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """A teacher's join link: students who sign up (or join while signed in) through it become their students."""
    if not cu.user.is_teacher:
        raise HTTPException(400, "Join links are for teachers")
    code = teachers.join_code(db, cu.user)
    return {"code": code, "url": f"{get_settings().app_url}/join/{code}",
            "students": db.scalar(select(func.count()).select_from(User).where(User.teacher_id == cu.user.id))}


@router.post("/join-link/regenerate")
def regenerate_join_link(cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """Replaces the link (the old one stops working). Students who already joined stay."""
    if not cu.user.is_teacher:
        raise HTTPException(400, "Join links are for teachers")
    teachers.join_code(db, cu.user, regenerate=True)
    return join_link(cu, db)


@router.get("/teachers", dependencies=[Depends(require_admin)])
def teacher_list(db: Session = Depends(get_db)):
    """Teachers and how many students each has (for assigning students)."""
    counts = dict(db.execute(select(User.teacher_id, func.count()).where(User.teacher_id.is_not(None))
                             .group_by(User.teacher_id)).all())
    rows = db.scalars(select(User).where(User.role == UserRole.TEACHER).order_by(User.first_name, User.last_name)).all()
    return [{"id": str(t.id), "name": t.full_name, "email": t.email, "is_active": t.is_active,
             "students": counts.get(t.id, 0)} for t in rows]
