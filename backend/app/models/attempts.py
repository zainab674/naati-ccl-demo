"""Student attempts: mock tests (2 dialogues), dialogue attempts, segment attempts, repeats."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, IdMixin
from .enums import AttemptResult, AttemptStatus, ScoringStatus, enum_col


class MockTestAttempt(IdMixin, Base):
    """Groups the DialogueAttempts of one mock test sitting. Total out of 90, per-dialogue minimum."""
    __tablename__ = "mock_test_attempts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    mock_test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_tests.id"))
    status: Mapped[AttemptStatus] = mapped_column(enum_col(AttemptStatus), default=AttemptStatus.IN_PROGRESS)
    scoring_status: Mapped[ScoringStatus] = mapped_column(enum_col(ScoringStatus), default=ScoringStatus.PENDING)
    maximum_score: Mapped[float] = mapped_column(default=90)
    passing_score: Mapped[float] = mapped_column(default=63)
    total_score: Mapped[float | None] = mapped_column(nullable=True)
    result: Mapped[AttemptResult | None] = mapped_column(enum_col(AttemptResult), nullable=True)
    # Where the student is in the player (info1 | info2 | segment | summary) so a reload resumes in place.
    current_step: Mapped[str] = mapped_column(String(20), default="info1")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user = relationship("User")
    mock_test = relationship("MockTest", lazy="joined")
    dialogue_attempts: Mapped[list["DialogueAttempt"]] = relationship(
        back_populates="mock_test_attempt", order_by="DialogueAttempt.position")


class DialogueAttempt(IdMixin, Base):
    __tablename__ = "dialogue_attempts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    dialogue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dialogues.id"), index=True)
    language_pair_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("language_pairs.id"))
    mock_test_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mock_test_attempts.id"), nullable=True, index=True)
    position: Mapped[int] = mapped_column(default=1)  # order within a mock test
    status: Mapped[AttemptStatus] = mapped_column(enum_col(AttemptStatus), default=AttemptStatus.IN_PROGRESS)
    current_segment_number: Mapped[int] = mapped_column(default=1)
    maximum_score: Mapped[float] = mapped_column(default=45)
    passing_score: Mapped[float] = mapped_column(default=29)
    accuracy_completeness_deduction: Mapped[float] = mapped_column(default=0)
    language_quality_deduction: Mapped[float] = mapped_column(default=0)
    fluency_deduction: Mapped[float] = mapped_column(default=0)
    total_deductions: Mapped[float] = mapped_column(default=0)
    total_score: Mapped[float | None] = mapped_column(nullable=True)
    total_repeats: Mapped[int] = mapped_column(default=0)
    result: Mapped[AttemptResult | None] = mapped_column(enum_col(AttemptResult), nullable=True)
    scoring_status: Mapped[ScoringStatus] = mapped_column(enum_col(ScoringStatus), default=ScoringStatus.PENDING)
    attempt_number: Mapped[int] = mapped_column(default=1)
    dialogue_version: Mapped[int] = mapped_column(default=1)
    overall_feedback: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    integrity_events: Mapped[list] = mapped_column(JSON, default=list)  # tab blur, reloads, mic denied

    user = relationship("User")
    dialogue = relationship("Dialogue", lazy="joined")
    mock_test_attempt: Mapped[MockTestAttempt | None] = relationship(back_populates="dialogue_attempts")
    segment_attempts: Mapped[list["SegmentAttempt"]] = relationship(
        back_populates="dialogue_attempt", cascade="all, delete-orphan", lazy="selectin",
        order_by="SegmentAttempt.segment_number")


class SegmentAttempt(IdMixin, Base):
    __tablename__ = "segment_attempts"
    dialogue_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dialogue_attempts.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("segments.id"))
    segment_number: Mapped[int] = mapped_column(Integer)  # denormalised for ordering
    source_language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"))
    target_language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"))
    audio_user: Mapped[str] = mapped_column(String(300), default="")       # storage key of the recording
    audio_mime: Mapped[str] = mapped_column(String(60), default="")
    audio_duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    transcript_user: Mapped[str] = mapped_column(Text, default="")
    stt_words: Mapped[list] = mapped_column(JSON, default=list)            # [{"word","start","end"}]
    stt_provider: Mapped[str] = mapped_column(String(40), default="")
    stt_model: Mapped[str] = mapped_column(String(80), default="")
    # Client timestamps (ms, relative to recording start): chime_end, record_start, record_stop; and VAD results.
    timing: Mapped[dict] = mapped_column(JSON, default=dict)
    play_count: Mapped[int] = mapped_column(default=0)
    record_count: Mapped[int] = mapped_column(default=0)
    accuracy_completeness_deduction: Mapped[float] = mapped_column(default=0)
    language_quality_deduction: Mapped[float] = mapped_column(default=0)
    fluency_deduction: Mapped[float] = mapped_column(default=0)
    total_deduction: Mapped[float] = mapped_column(default=0)
    ai_feedback: Mapped[str] = mapped_column(Text, default="")
    scoring_status: Mapped[ScoringStatus] = mapped_column(enum_col(ScoringStatus), default=ScoringStatus.PENDING)
    scoring_error: Mapped[str] = mapped_column(Text, default="")
    scoring_confidence: Mapped[float | None] = mapped_column(nullable=True)
    needs_review: Mapped[bool] = mapped_column(default=False)
    reviewed_by_admin: Mapped[bool] = mapped_column(default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    skipped: Mapped[bool] = mapped_column(default=False)

    dialogue_attempt: Mapped[DialogueAttempt] = relationship(back_populates="segment_attempts")
    segment = relationship("Segment", lazy="joined")
    accuracy_evaluations: Mapped[list["AccuracyCompletenessEvaluation"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan", lazy="selectin")
    language_quality_errors: Mapped[list["LanguageQualityError"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan", lazy="selectin")
    fluency_errors: Mapped[list["FluencyError"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan", lazy="selectin")
    admin_reviews: Mapped[list["AdminReview"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan", lazy="selectin", order_by="AdminReview.created_at")


class RepeatEvent(IdMixin, Base):
    __tablename__ = "repeat_events"
    dialogue_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dialogue_attempts.id", ondelete="CASCADE"), index=True)
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("segment_attempts.id", ondelete="CASCADE"))
    repeat_number: Mapped[int] = mapped_column(Integer)
