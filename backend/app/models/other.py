"""Courses, plans and payments, site content, imports, email log, job queue, content protection."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, IdMixin, utcnow
from .enums import ContentStatus, EmailStatus, ImportStatus, ImportType, JobStatus, enum_col

# ------------------------------------------------------------------ courses

class Course(IdMixin, Base):
    __tablename__ = "courses"
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ContentStatus] = mapped_column(enum_col(ContentStatus), default=ContentStatus.DRAFT)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_free: Mapped[bool] = mapped_column(default=False)

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="course", order_by="Lesson.lesson_number", cascade="all, delete-orphan")


class Lesson(IdMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("course_id", "lesson_number"),)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    lesson_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    video_url: Mapped[str] = mapped_column(String(1000), default="")
    html_content: Mapped[str] = mapped_column(Text, default="")  # sanitised on write
    is_free: Mapped[bool] = mapped_column(default=False)
    status: Mapped[ContentStatus] = mapped_column(enum_col(ContentStatus), default=ContentStatus.PUBLISHED)

    course: Mapped[Course] = relationship(back_populates="lessons")


class LessonProgress(IdMixin, Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    completed_at: Mapped[datetime] = mapped_column(default=utcnow)


# ------------------------------------------------------------------ plans and payments

class Plan(IdMixin, Base):
    __tablename__ = "plans"
    key: Mapped[str] = mapped_column(String(60), unique=True)        # self-study | coaching
    name: Mapped[str] = mapped_column(String(100))
    stripe_price_id: Mapped[str] = mapped_column(String(100), default="")
    price_display: Mapped[str] = mapped_column(String(60), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[list] = mapped_column(JSON, default=list)
    contact_only: Mapped[bool] = mapped_column(default=False)        # Coaching: "Contact us" until booking exists
    active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class Subscription(IdMixin, Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30))                   # raw Stripe status
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    last_event_at: Mapped[datetime | None] = mapped_column(nullable=True)  # newest Stripe event applied
    # "stripe", or "manual" for access granted by a teacher (status: active / trialing / revoked; period end = end date)
    source: Mapped[str] = mapped_column(String(20), default="stripe", server_default="stripe")
    granted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", server_default="")

    plan = relationship("Plan", lazy="joined")


class Payment(IdMixin, Base):
    __tablename__ = "payments"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[int] = mapped_column(default=0)                    # minor units (cents)
    currency: Mapped[str] = mapped_column(String(10), default="aud")
    status: Mapped[str] = mapped_column(String(30), default="paid")
    receipt_url: Mapped[str] = mapped_column(String(1000), default="")


class StripeEvent(IdMixin, Base):
    """Processed webhook events; the unique event id makes the webhook idempotent."""
    __tablename__ = "stripe_events"
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


# ------------------------------------------------------------------ site, imports, email

class SiteContent(IdMixin, Base):
    __tablename__ = "site_content"
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[dict | list] = mapped_column(JSON, default=dict)


class ImportJob(IdMixin, Base):
    __tablename__ = "import_jobs"
    type: Mapped[ImportType] = mapped_column(enum_col(ImportType))
    file_name: Mapped[str] = mapped_column(String(255))
    file_key: Mapped[str] = mapped_column(String(300), default="")    # uploaded CSV in storage
    status: Mapped[ImportStatus] = mapped_column(enum_col(ImportStatus))
    dry_run_report: Mapped[dict] = mapped_column(JSON, default=dict)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)        # media ingest progress
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EmailLog(IdMixin, Base):
    __tablename__ = "email_logs"
    to: Mapped[str] = mapped_column(String(255), index=True)
    template: Mapped[str] = mapped_column(String(60))
    subject: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[EmailStatus] = mapped_column(enum_col(EmailStatus))
    provider: Mapped[str] = mapped_column(String(30), default="")
    provider_id: Mapped[str] = mapped_column(String(200), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ------------------------------------------------------------------ background jobs

class Job(IdMixin, Base):
    """Postgres-backed job queue (SELECT ... FOR UPDATE SKIP LOCKED). No Redis needed."""
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(60), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[JobStatus] = mapped_column(enum_col(JobStatus), default=JobStatus.QUEUED, index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    run_after: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


# ------------------------------------------------------------------ content protection (from the demo)

class PlayGrant(IdMixin, Base):
    """One permission to stream one segment once. Bound to the segment attempt and the login session."""
    __tablename__ = "play_grants"
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segment_attempts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[datetime]
    key_fetches: Mapped[int] = mapped_column(default=0)


class SecurityEvent(IdMixin, Base):
    __tablename__ = "security_events"
    user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
