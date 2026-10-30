"""Student activity log (client brief, module 11). record() adds an event to the caller's transaction;
timeline() merges it with emails, payments and access grants that are already stored elsewhere."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ActivityEvent, EmailLog, Payment, Subscription, User

EMAIL_LABELS = {"welcome": "Welcome email", "receipt": "Payment receipt", "password_reset": "Password reset email",
                "enrolment_invite": "Invite to set a password", "results_ready": "Results-ready email",
                "message": "Message"}


def record(db: Session, user: User | uuid.UUID, kind: str, summary: str = "", **data) -> None:
    user_id = user.id if isinstance(user, User) else user
    db.add(ActivityEvent(user_id=user_id, kind=kind, summary=summary[:300],
                         data={k: str(v) for k, v in data.items() if v is not None}))


def timeline(db: Session, user_id: uuid.UUID, limit: int = 200) -> list[dict]:
    rows = [{"kind": e.kind, "summary": e.summary, "data": e.data, "at": e.created_at}
            for e in db.scalars(select(ActivityEvent).where(ActivityEvent.user_id == user_id)
                                .order_by(ActivityEvent.created_at.desc()).limit(limit))]
    for e in db.scalars(select(EmailLog).where(EmailLog.user_id == user_id).order_by(EmailLog.created_at.desc()).limit(limit)):
        label = EMAIL_LABELS.get(e.template, e.template)
        rows.append({"kind": "email", "summary": f"{label}: {e.subject}" if e.template == "message" else label,
                     "data": {"status": e.status.value, "error": e.error}, "at": e.created_at})
    for p in db.scalars(select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc()).limit(limit)):
        rows.append({"kind": "payment", "summary": f"Payment ${p.amount / 100:.2f} {p.currency.upper()} ({p.status})",
                     "data": {}, "at": p.created_at})
    for s in db.scalars(select(Subscription).where(Subscription.user_id == user_id)
                        .order_by(Subscription.created_at.desc()).limit(limit)):
        what = "Access changed by a teacher" if s.source == "manual" else f"Subscription {s.plan.name if s.plan else ''}".strip()
        rows.append({"kind": "access", "summary": f"{what} ({s.status})" + (f": {s.note}" if s.note else ""),
                     "data": {}, "at": s.created_at})
    rows.sort(key=lambda r: r["at"], reverse=True)
    return [{**r, "at": r["at"].isoformat()} for r in rows[:limit]]
