"""Public (no login) content for the marketing site."""
import json
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Language, LanguageType, RecordStatus, SiteContent
from ..settings import BASE_DIR

router = APIRouter(prefix="/api/public", tags=["public"])

CONTENT_KEYS = ("home", "faq", "reviews", "self-study", "coaching", "terms", "privacy")


@lru_cache
def default_content() -> dict:
    return json.loads((BASE_DIR / "content" / "site_content.json").read_text(encoding="utf-8"))


def get_content(db: Session, key: str):
    row = db.scalar(select(SiteContent).where(SiteContent.key == key))
    if row is not None:
        return row.value
    return default_content().get(key)


@router.get("/languages")
def languages(db: Session = Depends(get_db)):
    """Community languages (LOTEs) a student can choose; each is paired with English."""
    rows = db.scalars(select(Language).where(Language.language_type == LanguageType.LOTE,
                                             Language.status == RecordStatus.ACTIVE).order_by(Language.name))
    return [{"code": lang.code, "name": lang.name, "native_name": lang.native_name} for lang in rows]


@router.get("/content/{key}")
def content(key: str, db: Session = Depends(get_db)):
    if key not in CONTENT_KEYS:
        raise HTTPException(404, "Not found")
    return {"key": key, "value": get_content(db, key)}
