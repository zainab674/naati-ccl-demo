"""Admin/teacher messages to one or many students (client brief, module 11). Transactional, not marketing:
one email per student, queued as jobs so a large class does not block the request, each send in EmailLog."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..jobs import enqueue, handler
from ..models import User, UserRole
from ..settings import get_settings
from .email import send_template

SEND_MESSAGE = "send_student_message"
MAX_RECIPIENTS = 2000


class MessageError(ValueError):
    pass


def personalise(text: str, user: User) -> str:
    """{first_name} and {name} are replaced per student; other braces are left as typed."""
    return text.replace("{first_name}", user.first_name).replace("{name}", user.full_name)


def queue_message(db: Session, user_ids: list[uuid.UUID], subject: str, body: str, sender: User) -> int:
    """Queues one email per active student. Returns how many were queued (inactive or unknown ids are skipped)."""
    if not subject.strip() or not body.strip():
        raise MessageError("Write a subject and a message")
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        raise MessageError("Choose at least one student")
    if len(ids) > MAX_RECIPIENTS:
        raise MessageError(f"At most {MAX_RECIPIENTS} students per message")
    students = db.scalars(select(User).where(User.id.in_(ids), User.role == UserRole.STUDENT, User.is_active)).all()
    for u in students:
        enqueue(db, SEND_MESSAGE, {"user_id": str(u.id), "subject": subject.strip(), "body": body,
                                   "sender": sender.full_name}, max_attempts=1)
    db.commit()
    return len(students)


@handler(SEND_MESSAGE)
def send_message_job(payload: dict) -> None:
    with SessionLocal() as db:
        u = db.get(User, uuid.UUID(payload["user_id"]))
        if not u or not u.is_active:
            return
        send_template(db, "message", u.email, {
            "subject": personalise(payload["subject"], u), "body": personalise(payload["body"], u),
            "sender": payload.get("sender", ""), "dashboard_url": f"{get_settings().app_url}/dashboard"}, user_id=u.id)
