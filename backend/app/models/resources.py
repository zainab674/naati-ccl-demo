"""Learning hub: ebooks, glossaries, worksheets, audio, video, articles and links (MVP_SPEC module 15)."""
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base, IdMixin
from .enums import ContentStatus, ResourceType, enum_col


class Resource(IdMixin, Base):
    """One study resource. Content is one of: a private file (served only through /api/resources/{id}/file), an
    article (sanitised HTML), or an external URL."""
    __tablename__ = "resources"
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    resource_type: Mapped[ResourceType] = mapped_column(enum_col(ResourceType))
    # None = for every language.
    language_pair_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("language_pairs.id"), nullable=True, index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    status: Mapped[ContentStatus] = mapped_column(enum_col(ContentStatus), default=ContentStatus.DRAFT)
    is_free: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    file_key: Mapped[str] = mapped_column(String(400), default="")       # storage key; never exposed to students
    file_name: Mapped[str] = mapped_column(String(255), default="")
    file_size: Mapped[int] = mapped_column(default=0)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    external_url: Mapped[str] = mapped_column(String(1000), default="")
    html_content: Mapped[str] = mapped_column(Text, default="")          # sanitised on write
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    language_pair = relationship("LanguagePair", lazy="joined")
    topic = relationship("Topic", lazy="joined")
