"""Manual enrolment by teachers/admins: create students without Stripe, grant or revoke access with an optional end
date, invite them to set a password, and bulk-enrol from a CSV.

A manual grant is a Subscription row with source="manual" (status active / trialing / revoked, current_period_end =
end date), so the student's admin page shows Stripe and manual history together. The User row carries the effective
state (subscription_status + access_expires_at); deps.effective_status() treats a passed end date as Expired.
"""
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import Language, PasswordResetToken, Subscription, SubscriptionStatus, User, UserRole
from ..security import hash_password, new_reset_token
from ..settings import get_settings
from . import languages
from .email import send_template
from .imports.common import CsvError, Report, read_csv

MANUAL = "manual"
ACCESS_CHOICES = {"Active": SubscriptionStatus.ACTIVE, "Trial": SubscriptionStatus.TRIAL, "None": SubscriptionStatus.INACTIVE}
GRANT_STATUS = {SubscriptionStatus.ACTIVE: "active", SubscriptionStatus.TRIAL: "trialing", SubscriptionStatus.INACTIVE: "revoked"}

BULK_COLUMNS = ["first_name", "email"]
BULK_OPTIONAL = ["last_name", "language", "access", "access_until", "target_exam_date", "note"]


class EnrolmentError(ValueError):
    pass


def end_of_day(d: date) -> datetime:
    """Access "until 30 Nov" includes all of 30 Nov in the business time zone (APP_TIMEZONE)."""
    return datetime.combine(d, time(23, 59, 59), tzinfo=ZoneInfo(get_settings().app_timezone))


def normalise_email(email: str) -> str:
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as e:
        raise EnrolmentError(f"Invalid email address: {email}") from e


def manual_grant(db: Session, user: User) -> Subscription | None:
    """The newest access record, if it is a manual one."""
    row = db.scalars(select(Subscription).where(Subscription.user_id == user.id)
                     .order_by(Subscription.created_at.desc()).limit(1)).first()
    return row if row and row.source == MANUAL else None


def access_is_manual(db: Session, user: User) -> bool:
    row = manual_grant(db, user)
    return bool(row and row.status != "revoked")


def stripe_managed(db: Session, user: User) -> bool:
    """True while a Stripe subscription is live: Stripe events will overwrite manual changes."""
    return bool(db.scalar(select(Subscription.id).where(
        Subscription.user_id == user.id, Subscription.source != MANUAL,
        Subscription.status.in_(("active", "trialing", "past_due", "unpaid", "incomplete")))))


def grant_access(db: Session, user: User, access: str, until: date | None, by: User, note: str = "") -> Subscription:
    """Set (or remove) a student's access by hand. Recorded as a manual Subscription row."""
    if access not in ACCESS_CHOICES:
        raise EnrolmentError(f"Access must be one of {', '.join(ACCESS_CHOICES)}")
    status = ACCESS_CHOICES[access]
    expires = end_of_day(until) if until and status != SubscriptionStatus.INACTIVE else None
    if expires and expires <= utcnow():
        raise EnrolmentError("The access end date must be today or later")
    user.subscription_status, user.access_expires_at = status, expires
    row = Subscription(user_id=user.id, source=MANUAL, status=GRANT_STATUS[status], current_period_end=expires,
                       granted_by_id=by.id, note=note.strip()[:2000])
    db.add(row)
    return row


def send_invite(db: Session, user: User) -> None:
    """Email a single-use link to set a password (a reset token with a longer expiry)."""
    s = get_settings()
    token, token_hash = new_reset_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash,
                              expires_at=utcnow() + timedelta(hours=s.enrolment_invite_hours)))
    db.commit()
    send_template(db, "enrolment_invite", user.email, {
        "first_name": user.first_name, "expires_hours": s.enrolment_invite_hours,
        "invite_url": f"{s.app_url}/reset-password?token={token}&invite=1"}, user_id=user.id)


@dataclass
class NewStudent:
    first_name: str
    email: str
    last_name: str = ""
    language: Language | None = None
    access: str = "None"
    access_until: date | None = None
    target_exam_date: date | None = None
    note: str = ""
    password: str | None = None


def create_student(db: Session, spec: NewStudent, by: User) -> User:
    email = normalise_email(spec.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise EnrolmentError(f"An account with {email} already exists")
    user = User(first_name=spec.first_name.strip(), last_name=spec.last_name.strip(), email=email, role=UserRole.STUDENT,
                # Without a password the account cannot be signed in to until the invite link is used.
                password_hash=hash_password(spec.password or secrets.token_urlsafe(32)),
                preferred_language_id=spec.language.id if spec.language else None,
                target_exam_date=spec.target_exam_date, enrolled_by_id=by.id)
    db.add(user)
    db.flush()
    if spec.access != "None" or spec.note:
        grant_access(db, user, spec.access, spec.access_until, by, spec.note)
    return user


# ------------------------------------------------------------------ bulk CSV

def _date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(value)


def parse_bulk(db: Session, data: bytes) -> tuple[list[NewStudent], Report]:
    """Validate a students CSV. Rows with errors are reported and not created; existing emails are skipped."""
    report = Report()
    try:
        rows = read_csv(data, BULK_COLUMNS, BULK_OPTIONAL)
    except CsvError as e:
        report.error(None, "", str(e))
        return [], report
    if rows[0].get("_unknown_columns"):
        report.warn(1, "", f"Ignored unknown column(s): {', '.join(rows[0]['_unknown_columns'])}")
    lotes = languages.lotes_by_code(db)
    existing = set(db.scalars(select(User.email)))
    seen: set[str] = set()
    out, skipped = [], 0
    for row in rows:
        n, errs = row["_row"], []
        try:
            email = normalise_email(row["email"])
        except EnrolmentError as e:
            report.error(n, "email", str(e))
            continue
        if email in seen:
            report.error(n, "email", f"{email} appears more than once in the file")
            continue
        seen.add(email)
        if email in existing:
            report.warn(n, "email", f"{email} already has an account; skipped")
            skipped += 1
            continue
        if not row["first_name"]:
            errs.append(("first_name", "Required"))
        code = row.get("language", "").lower()
        lang = lotes.get(code) if code else None
        if code and not lang:
            errs.append(("language", f"Unknown language code '{code}' (use one of: {', '.join(sorted(lotes))})"))
        access = (row.get("access") or "None").strip().title()
        if access not in ACCESS_CHOICES:
            errs.append(("access", "Use Active, Trial or None"))
        until = exam = None
        try:
            until = _date(row.get("access_until", ""))
        except ValueError:
            errs.append(("access_until", "Use YYYY-MM-DD or DD/MM/YYYY"))
        try:
            exam = _date(row.get("target_exam_date", ""))
        except ValueError:
            errs.append(("target_exam_date", "Use YYYY-MM-DD or DD/MM/YYYY"))
        if until and end_of_day(until) <= utcnow():
            errs.append(("access_until", "Date is in the past"))
        for col, msg in errs:
            report.error(n, col, msg)
        if not errs:
            out.append(NewStudent(first_name=row["first_name"], last_name=row.get("last_name", ""), email=email,
                                  language=lang, access=access, access_until=until, target_exam_date=exam,
                                  note=row.get("note", "")))
    report.summary = {"rows": len(rows), "to_create": len(out), "skipped_existing": skipped}
    return out, report

