"""Scoring records. Deduction values are written by the platform from config, never taken from the model."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, IdMixin
from .enums import (
    AccuracyResult,
    DetectionMethod,
    EvaluationType,
    FluencyType,
    LanguageQualityType,
    ReviewStatus,
    RunStatus,
    enum_col,
)


class AccuracyCompletenessEvaluation(IdMixin, Base):
    __tablename__ = "accuracy_completeness_evaluations"
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segment_attempts.id", ondelete="CASCADE"), index=True)
    evaluation_type: Mapped[EvaluationType] = mapped_column(enum_col(EvaluationType))
    meaning_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meaning_units.id"), nullable=True)
    result: Mapped[AccuracyResult] = mapped_column(enum_col(AccuracyResult))
    source_meaning: Mapped[str] = mapped_column(Text, default="")
    student_meaning: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    suggested_version: Mapped[str] = mapped_column(Text, default="")
    deduction: Mapped[float] = mapped_column(default=0)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    # Meaning Unit weight at scoring time: later edits to the MU must not change scores already given.
    weight: Mapped[float] = mapped_column(default=1)
    detection_method: Mapped[DetectionMethod] = mapped_column(enum_col(DetectionMethod), default=DetectionMethod.AI)


class LanguageQualityError(IdMixin, Base):
    __tablename__ = "language_quality_errors"
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segment_attempts.id", ondelete="CASCADE"), index=True)
    language_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("languages.id"), nullable=True)
    error_type: Mapped[LanguageQualityType] = mapped_column(enum_col(LanguageQualityType))
    student_text: Mapped[str] = mapped_column(Text, default="")
    suggested_version: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    timestamp_seconds: Mapped[float | None] = mapped_column(nullable=True)
    deduction: Mapped[float] = mapped_column(default=0)
    detection_method: Mapped[DetectionMethod] = mapped_column(enum_col(DetectionMethod), default=DetectionMethod.AI)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    needs_review: Mapped[bool] = mapped_column(default=False)


class FluencyError(IdMixin, Base):
    __tablename__ = "fluency_errors"
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segment_attempts.id", ondelete="CASCADE"), index=True)
    language_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("languages.id"), nullable=True)
    error_type: Mapped[FluencyType] = mapped_column(enum_col(FluencyType))
    timestamp_seconds: Mapped[float | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    transcript_excerpt: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    deduction: Mapped[float] = mapped_column(default=0)
    detection_method: Mapped[DetectionMethod] = mapped_column(enum_col(DetectionMethod), default=DetectionMethod.AI)
    confidence: Mapped[float | None] = mapped_column(nullable=True)


class AIScoringRun(IdMixin, Base):
    """Every model call (STT and evaluation), for audit and debugging."""
    __tablename__ = "ai_scoring_runs"
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segment_attempts.id", ondelete="CASCADE"), index=True)
    source_language_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("languages.id"), nullable=True)
    target_language_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("languages.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="evaluation")  # stt | evaluation
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40), default="")
    request_data: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_response: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    processed_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[RunStatus] = mapped_column(enum_col(RunStatus), default=RunStatus.PENDING)
    error_message: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class LanguageScoringConfig(IdMixin, Base):
    __tablename__ = "language_scoring_configs"
    language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"), index=True)
    grammar_guidelines: Mapped[str] = mapped_column(Text, default="")
    register_guidelines: Mapped[str] = mapped_column(Text, default="")
    hesitation_markers: Mapped[list] = mapped_column(JSON, default=list)
    pronunciation_config: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_prompt_addition: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)


class AdminReview(IdMixin, Base):
    """Admin override of one deduction (target_type/target_id) or of the segment as a whole."""
    __tablename__ = "admin_reviews"
    segment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segment_attempts.id", ondelete="CASCADE"), index=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(String(30), default="segment")  # accuracy | language | fluency | segment
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    original_deduction: Mapped[float] = mapped_column(default=0)
    revised_deduction: Mapped[float] = mapped_column(default=0)
    review_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ReviewStatus] = mapped_column(enum_col(ReviewStatus), default=ReviewStatus.REVIEWED)
