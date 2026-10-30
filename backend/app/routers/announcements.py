"""Dashboard announcements carousel (MVP scope, module 4): live sessions, 1-on-1 classes and news.
Students read them through /api/dashboard; admins manage them here."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import require_admin
from ..models import Announcement, ContentStatus, LanguagePair, User
from ..services import languages
from ..settings import ccl_config

admin = APIRouter(prefix="/api/admin/announcements", tags=["admin"], dependencies=[Depends(require_admin)])

KINDS = {"live_session": "Live session", "class": "1-on-1 class", "news": "News"}


def as_dict(a: Announcement) -> dict:
    lote = a.language_pair.lote if a.language_pair else None
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {"id": str(a.id), "kind": a.kind, "kind_label": KINDS.get(a.kind, a.kind), "title": a.title, "body": a.body,
            "event_at": iso(a.event_at), "link_url": a.link_url, "link_label": a.link_label,
            "starts_at": iso(a.starts_at), "ends_at": iso(a.ends_at), "language": lote.code if lote else None,
            "language_name": lote.name if lote else None, "status": a.status.value, "sort_order": a.sort_order}


def for_student(db: Session, user: User) -> list[dict]:
    """Published, inside their date window, for every language or the student's own (all if none chosen)."""
    now = utcnow()
    q = (select(Announcement).where(Announcement.status == ContentStatus.PUBLISHED,
                                    or_(Announcement.starts_at.is_(None), Announcement.starts_at <= now),
                                    or_(Announcement.ends_at.is_(None), Announcement.ends_at > now))
         .order_by(Announcement.sort_order, Announcement.event_at.nulls_last(), Announcement.created_at.desc()))
    pair = languages.pair_for(db, user.preferred_language) if user.preferred_language else None
    if pair:
        q = q.where(or_(Announcement.language_pair_id.is_(None), Announcement.language_pair_id == pair.id))
    limit = int(ccl_config().get("dashboard", {}).get("announcements_max", 6))
    return [as_dict(a) for a in db.scalars(q.limit(limit))]


class AnnouncementIn(BaseModel):
    kind: str = "news"
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=1000)
    event_at: datetime | None = None
    link_url: str = Field(default="", max_length=1000)
    link_label: str = Field(default="", max_length=60)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    language: str | None = None  # LOTE code; None = every language
    status: ContentStatus = ContentStatus.DRAFT
    sort_order: int = 0


def _apply(db: Session, a: Announcement, body: AnnouncementIn) -> None:
    if body.kind not in KINDS:
        raise HTTPException(400, f"Kind must be one of {', '.join(KINDS)}")
    url = body.link_url.strip()
    if url and not (url.startswith(("https://", "http://")) or (url.startswith("/") and not url.startswith("//"))):
        raise HTTPException(400, "Link must start with https:// or be a page on this site such as /courses")
    if body.starts_at and body.ends_at and body.ends_at <= body.starts_at:
        raise HTTPException(400, "The end date must be after the start date")
    pair: LanguagePair | None = None
    if body.language:
        lote = languages.lote_by_code(db, body.language)
        if not lote:
            raise HTTPException(400, f"Unknown language code '{body.language}'")
        pair = languages.pair_for(db, lote)
    a.kind, a.title, a.body = body.kind, body.title.strip(), body.body.strip()
    a.event_at, a.link_url, a.link_label = body.event_at, url, body.link_label.strip()
    a.starts_at, a.ends_at, a.status, a.sort_order = body.starts_at, body.ends_at, body.status, body.sort_order
    a.language_pair_id = pair.id if pair else None


@admin.get("")
def list_announcements(db: Session = Depends(get_db)):
    rows = db.scalars(select(Announcement).order_by(Announcement.sort_order, Announcement.created_at.desc())).all()
    return [as_dict(a) for a in rows]


@admin.post("", status_code=201)
def create(body: AnnouncementIn, db: Session = Depends(get_db)):
    a = Announcement(title="")
    _apply(db, a, body)
    db.add(a)
    db.commit()
    return as_dict(a)


def _get(db: Session, ann_id: uuid.UUID) -> Announcement:
    a = db.get(Announcement, ann_id)
    if not a:
        raise HTTPException(404, "Announcement not found")
    return a


@admin.put("/{ann_id}")
def update(ann_id: uuid.UUID, body: AnnouncementIn, db: Session = Depends(get_db)):
    a = _get(db, ann_id)
    _apply(db, a, body)
    db.commit()
    return as_dict(a)


@admin.delete("/{ann_id}")
def delete(ann_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(_get(db, ann_id))
    db.commit()
    return {"ok": True}
