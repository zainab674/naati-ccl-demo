"""Files kept in the database (STORAGE_BACKEND=db): for hosts without a disk or object storage, e.g. Vercel."""
from datetime import datetime

from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class StoredObject(Base):
    __tablename__ = "stored_objects"
    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
