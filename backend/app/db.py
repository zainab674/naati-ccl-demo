import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .settings import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), uuid.UUID: Uuid}


class IdMixin:
    """UUID primary key + created_at/updated_at on every table (DATA_MODEL.md)."""
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


def make_engine(url: str | None = None):
    return create_engine(url or get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
