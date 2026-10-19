"""Languages, topics, dialogues, segments, meaning units, mock test definitions."""
import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, IdMixin
from .enums import ContentStatus, Difficulty, Direction, LanguageType, RecordStatus, enum_col


class Language(IdMixin, Base):
    __tablename__ = "languages"
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(10), unique=True)          # e.g. "en", "fil"
    native_name: Mapped[str] = mapped_column(String(80), default="")
    language_type: Mapped[LanguageType] = mapped_column(enum_col(LanguageType))
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)
    supports_speech_to_text: Mapped[bool] = mapped_column(default=True)
    supports_text_to_speech: Mapped[bool] = mapped_column(default=False)
    stt_code: Mapped[str] = mapped_column(String(10), default="")       # STT language hint, e.g. "tl" for Filipino


class LanguagePair(IdMixin, Base):
    """English <-> one LOTE. Validation (English/LOTE types, no duplicates) in services/content.py."""
    __tablename__ = "language_pairs"
    __table_args__ = (UniqueConstraint("english_language_id", "lote_language_id"),)
    english_language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"))
    lote_language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"))
    display_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)

    english = relationship("Language", foreign_keys=[english_language_id], lazy="joined")
    lote = relationship("Language", foreign_keys=[lote_language_id], lazy="joined")


class Topic(IdMixin, Base):
    __tablename__ = "topics"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RecordStatus] = mapped_column(enum_col(RecordStatus), default=RecordStatus.ACTIVE)
    sort_order: Mapped[int] = mapped_column(default=0)


class Dialogue(IdMixin, Base):
    __tablename__ = "dialogues"
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)   # CSV idempotency key
    title: Mapped[str] = mapped_column(String(200))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    language_pair_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("language_pairs.id"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[Difficulty] = mapped_column(enum_col(Difficulty), default=Difficulty.INTERMEDIATE)
    instructions: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ContentStatus] = mapped_column(enum_col(ContentStatus), default=ContentStatus.DRAFT)
    maximum_score: Mapped[float] = mapped_column(default=45)
    passing_score: Mapped[float] = mapped_column(default=29)
    estimated_duration: Mapped[int | None] = mapped_column(nullable=True)  # seconds
    sort_order: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    is_free: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    topic = relationship("Topic", lazy="joined")
    language_pair = relationship("LanguagePair", lazy="joined")
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="dialogue", order_by="Segment.segment_number", cascade="all, delete-orphan")


class Segment(IdMixin, Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("dialogue_id", "segment_number"),)
    dialogue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dialogues.id", ondelete="CASCADE"), index=True)
    segment_number: Mapped[int] = mapped_column(Integer)
    source_language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"))
    target_language_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("languages.id"))
    audio_file: Mapped[str] = mapped_column(String(300), default="")       # storage prefix of the HLS package
    source_audio_url: Mapped[str] = mapped_column(String(1000), default="")  # imported from CSV
    source_audio_hash: Mapped[str] = mapped_column(String(64), default="")   # skip re-processing unchanged audio
    media_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|processing|ready|failed
    media_error: Mapped[str] = mapped_column(Text, default="")
    transcript: Mapped[str] = mapped_column(Text, default="")
    speaker_label: Mapped[str] = mapped_column(String(80), default="")
    speaker_role: Mapped[str] = mapped_column(String(80), default="")
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    word_count: Mapped[int | None] = mapped_column(nullable=True)
    waveform_image: Mapped[str] = mapped_column(String(300), default="")   # storage key
    waveform_source_url: Mapped[str] = mapped_column(String(1000), default="")
    active: Mapped[bool] = mapped_column(default=True)

    dialogue: Mapped[Dialogue] = relationship(back_populates="segments")
    source_language = relationship("Language", foreign_keys=[source_language_id], lazy="joined")
    target_language = relationship("Language", foreign_keys=[target_language_id], lazy="joined")
    meaning_units: Mapped[list["MeaningUnit"]] = relationship(
        back_populates="segment", order_by="MeaningUnit.meaning_unit_number", cascade="all, delete-orphan")

    @property
    def direction(self) -> Direction:
        from .enums import LanguageType
        return (Direction.EN_TO_LOTE if self.source_language.language_type == LanguageType.ENGLISH
                else Direction.LOTE_TO_EN)


class MeaningUnit(IdMixin, Base):
    __tablename__ = "meaning_units"
    __table_args__ = (UniqueConstraint("segment_id", "meaning_unit_number"),)
    segment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("segments.id", ondelete="CASCADE"), index=True)
    meaning_unit_number: Mapped[int] = mapped_column(Integer)
    meaning: Mapped[str] = mapped_column(Text)
    reference_interpretation: Mapped[str] = mapped_column(Text, default="")
    reference_language_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("languages.id"), nullable=True)
    weight: Mapped[float] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)

    segment: Mapped[Segment] = relationship(back_populates="meaning_units")


class MockTest(IdMixin, Base):
    """A named mock test: an ordered set of dialogues (2 for a CCL mock)."""
    __tablename__ = "mock_tests"
    key: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    language_pair_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("language_pairs.id"))
    status: Mapped[ContentStatus] = mapped_column(enum_col(ContentStatus), default=ContentStatus.DRAFT)
    is_free: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    dialogues: Mapped[list["MockTestDialogue"]] = relationship(
        order_by="MockTestDialogue.position", cascade="all, delete-orphan", lazy="selectin")


class MockTestDialogue(IdMixin, Base):
    __tablename__ = "mock_test_dialogues"
    __table_args__ = (UniqueConstraint("mock_test_id", "position"),)
    mock_test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_tests.id", ondelete="CASCADE"))
    dialogue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dialogues.id"))
    position: Mapped[int] = mapped_column(Integer)

    dialogue = relationship("Dialogue", lazy="joined")
