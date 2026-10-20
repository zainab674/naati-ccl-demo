import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, IdMixin
from .enums import SubscriptionStatus, UserRole, enum_col


class User(IdMixin, Base):
    __tablename__ = "users"
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_col(UserRole), default=UserRole.STUDENT)
    preferred_language_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("languages.id"), nullable=True)
    target_exam_date: Mapped[date | None] = mapped_column(nullable=True)
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        enum_col(SubscriptionStatus), default=SubscriptionStatus.INACTIVE)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    flagged: Mapped[bool] = mapped_column(default=False)  # content-protection anomaly flag (from the demo)
    session_version: Mapped[int] = mapped_column(default=0)  # bump to sign out every session (password reset)
    # Set by a manual (teacher) grant with an end date: paid access stops at this time. Cleared when Stripe takes over.
    access_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    enrolled_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # manual enrolment

    preferred_language = relationship("Language")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


class PasswordResetToken(IdMixin, Base):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of the emailed token
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
