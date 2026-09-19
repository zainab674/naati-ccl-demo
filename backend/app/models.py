import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # student | assessor
    name: Mapped[str] = mapped_column(String(120))
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # CCL LOTE, e.g. "hi"
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Activity(Base):
    """One CCL dialogue. `type` keeps the core exam-agnostic (OET etc. later)."""
    __tablename__ = "activities"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(30), default="ccl_dialogue")
    title: Mapped[str] = mapped_column(String(200))
    scenario: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(60))
    difficulty: Mapped[str] = mapped_column(String(20))
    language_pair: Mapped[str] = mapped_column(String(20), default="hi-en")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)  # speakers etc.
    status: Mapped[str] = mapped_column(String(20), default="published")  # processing|published|failed
    status_detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="activity", order_by="Segment.order", cascade="all, delete-orphan"
    )


class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(10))   # en | hi (source language)
    source_text: Mapped[str] = mapped_column(Text)
    reference_text: Mapped[str] = mapped_column(Text)
    sample_student_text: Mapped[str] = mapped_column(Text, default="")  # seed only
    asset_key: Mapped[str] = mapped_column(String(200), default="")     # media dir
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    activity: Mapped[Activity] = relationship(back_populates="segments")

    @property
    def target_language(self) -> str:
        return "hi" if self.speaker == "en" else "en"


class MockTest(Base):
    __tablename__ = "mock_tests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    activity_ids: Mapped[list] = mapped_column(JSON)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(10))  # practice | mock
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id"), nullable=True)
    mock_test_id: Mapped[str | None] = mapped_column(ForeignKey("mock_tests.id"), nullable=True)
    # Flattened ordered list of {"activity_id", "segment_id"}
    plan_json: Mapped[list] = mapped_column(JSON, default=list)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    plays_json: Mapped[dict] = mapped_column(JSON, default=dict)  # {index: plays}
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    # in_progress | marking | marked | error
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    integrity_events_json: Mapped[list] = mapped_column(JSON, default=list)
    user: Mapped[User] = relationship()
    responses: Mapped[list["SegmentResponse"]] = relationship(
        back_populates="attempt", order_by="SegmentResponse.seg_index", cascade="all, delete-orphan"
    )


class PlayGrant(Base):
    """One permission to stream one segment once. Bound to attempt + login session."""
    __tablename__ = "play_grants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), index=True)
    seg_index: Mapped[int] = mapped_column(Integer)
    segment_id: Mapped[str] = mapped_column(String(32))
    session_id: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    key_fetches: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SegmentResponse(Base):
    __tablename__ = "segment_responses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), index=True)
    seg_index: Mapped[int] = mapped_column(Integer)
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.id"))
    audio_key: Mapped[str] = mapped_column(String(300), default="")
    audio_mime: Mapped[str] = mapped_column(String(60), default="audio/webm")
    transcript: Mapped[str] = mapped_column(Text, default="")
    stt_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    stt_provider: Mapped[str] = mapped_column(String(20), default="")
    stt_words_json: Mapped[list] = mapped_column(JSON, default=list)
    delivery_json: Mapped[dict] = mapped_column(JSON, default=dict)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded|marked|error
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    attempt: Mapped[Attempt] = relationship(back_populates="responses")
    segment: Mapped[Segment] = relationship()
    markings: Mapped[list["Marking"]] = relationship(
        back_populates="response", order_by="Marking.created_at", cascade="all, delete-orphan"
    )

    @property
    def effective_marking(self) -> "Marking | None":
        """Latest assessor override wins, else latest AI marking."""
        assessor = [m for m in self.markings if m.source == "assessor"]
        if assessor:
            return assessor[-1]
        return self.markings[-1] if self.markings else None


class Marking(Base):
    __tablename__ = "markings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    response_id: Mapped[str] = mapped_column(ForeignKey("segment_responses.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # ai | assessor
    marker: Mapped[str] = mapped_column(String(40), default="")  # claude-opus-5 | heuristic | name
    issues_json: Mapped[list] = mapped_column(JSON, default=list)
    points_deducted: Mapped[float] = mapped_column(Float, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_model_json: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    response: Mapped[SegmentResponse] = relationship(back_populates="markings")


class IssueReport(Base):
    __tablename__ = "issue_reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user: Mapped[User] = relationship()
    activity: Mapped[Activity] = relationship()


class SecurityEvent(Base):
    """Content-protection log: denied media requests, rate-limit hits, anomalies."""
    __tablename__ = "security_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class StoredFile(Base):
    """Runtime-written files (recordings, content-studio audio). Serverless has no disk."""
    __tablename__ = "stored_files"
    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(80), default="application/octet-stream")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
