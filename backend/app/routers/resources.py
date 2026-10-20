"""Learning hub: students browse and open study resources; admins manage them."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, ensure_access, is_locked, require_admin
from ..models import ContentStatus, Resource, ResourceType, Topic
from ..services import languages, ratelimit
from ..services import resources as svc
from ..services.html import sanitize
from ..services.storage import get_storage
from ..settings import get_settings

router = APIRouter(prefix="/api", tags=["resources"])
admin = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _lang(r: Resource) -> dict:
    lote = r.language_pair.lote if r.language_pair else None
    return {"language": lote.code if lote else None, "language_name": lote.name if lote else None}


def summary(r: Resource, user=None) -> dict:
    out = {"id": str(r.id), "title": r.title, "description": r.description, "type": r.resource_type.value,
           "topic": r.topic.name if r.topic else None, "is_free": r.is_free, **_lang(r),
           "has_file": bool(r.file_key), "file_name": r.file_name, "file_size": r.file_size,
           "content_type": r.content_type, "has_link": bool(r.external_url)}
    if user is not None:
        out["locked"] = is_locked(user, r.is_free)
    return out


# ------------------------------------------------------------------ students

def _file_headers(r: Resource) -> dict:
    # Same-origin framing only, so the hub page can show a PDF inline (the API default is DENY).
    return {"Content-Disposition": svc.disposition(r), "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-ancestors 'self'"}


def _published(db: Session, resource_id: uuid.UUID) -> Resource:
    r = db.get(Resource, resource_id)
    if not r or r.status != ContentStatus.PUBLISHED:
        raise HTTPException(404, "Resource not found")
    return r


@router.get("/resources")
def list_resources(type: str = "", language: str = "", cu: CurrentUser = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Resources for every language plus the chosen one ("" = the student's own language, "all" = everything)."""
    query = select(Resource).where(Resource.status == ContentStatus.PUBLISHED).order_by(Resource.sort_order, Resource.title)
    if type:
        try:
            query = query.where(Resource.resource_type == ResourceType(type))
        except ValueError as e:
            raise HTTPException(400, f"Unknown resource type '{type}'") from e
    try:
        pair = languages.student_pair(db, cu.user, language)
    except languages.LanguageRuleError as e:
        raise HTTPException(400, str(e)) from e
    if pair:
        query = query.where(or_(Resource.language_pair_id.is_(None), Resource.language_pair_id == pair.id))
    return [summary(r, cu.user) for r in db.scalars(query)]


@router.get("/resources/{resource_id}")
def get_resource(resource_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    r = _published(db, resource_id)
    ensure_access(cu.user, r.is_free)
    return {**summary(r, cu.user), "html_content": r.html_content, "external_url": r.external_url,  # sanitised on write
            "file_url": f"/api/resources/{r.id}/file" if r.file_key else None}


@router.get("/resources/{resource_id}/file")
def resource_file(resource_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    r = _published(db, resource_id)
    ensure_access(cu.user, r.is_free)
    ratelimit.enforce(f"resource-file:{cu.id}", 60)  # a person reading does not open 60 files a minute
    data = get_storage().get(r.file_key) if r.file_key else None
    if data is None:
        raise HTTPException(404, "File not found")
    return Response(data, media_type=r.content_type, headers=_file_headers(r))


# ------------------------------------------------------------------ admin

class ResourceIn(BaseModel):
    key: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,118}$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    type: ResourceType | None = None
    language: str | None = None  # LOTE code; None/"" = every language
    topic: str | None = None     # topic name; None/"" = none
    status: ContentStatus | None = None
    is_free: bool | None = None
    sort_order: int | None = None
    external_url: str | None = Field(default=None, max_length=1000)
    html_content: str | None = None


def admin_dict(r: Resource) -> dict:
    return {**summary(r), "key": r.key, "status": r.status.value, "sort_order": r.sort_order,
            "external_url": r.external_url, "html_content": r.html_content, "updated_at": r.updated_at.isoformat(),
            "problems": svc.readiness_problems(r)}


def _apply(db: Session, r: Resource, body: ResourceIn) -> None:
    fields = body.model_fields_set
    if "key" in fields and body.key and body.key != r.key:
        if db.scalar(select(Resource.id).where(Resource.key == body.key, Resource.id != r.id)):
            raise HTTPException(409, "A resource with this key already exists")
        r.key = body.key
    for name in ("title", "description", "is_free", "sort_order"):
        if name in fields and getattr(body, name) is not None:
            setattr(r, name, getattr(body, name))
    if "type" in fields and body.type:
        r.resource_type = body.type
    if "external_url" in fields:
        r.external_url = (body.external_url or "").strip()
    if "html_content" in fields:
        r.html_content = sanitize(body.html_content or "")
    if "language" in fields:
        lote = languages.lote_by_code(db, body.language) if body.language else None
        if body.language and not lote:
            raise HTTPException(400, f"Unknown language '{body.language}'")
        r.language_pair_id = languages.pair_for(db, lote).id if lote else None
    if "topic" in fields:
        topic = db.scalar(select(Topic).where(Topic.name == body.topic)) if body.topic else None
        if body.topic and not topic:
            raise HTTPException(400, f"Unknown topic '{body.topic}'")
        r.topic_id = topic.id if topic else None
    if "status" in fields and body.status:
        r.status = body.status
    if r.status == ContentStatus.PUBLISHED and (problems := svc.readiness_problems(r)):
        raise HTTPException(400, "Cannot publish yet: " + "; ".join(problems))


def _get(db: Session, resource_id: uuid.UUID) -> Resource:
    r = db.get(Resource, resource_id)
    if not r:
        raise HTTPException(404, "Resource not found")
    return r


@admin.get("/resources")
def admin_list(db: Session = Depends(get_db)):
    return [admin_dict(r) for r in db.scalars(select(Resource).order_by(Resource.sort_order, Resource.title))]


@admin.post("/resources", status_code=201)
def admin_create(body: ResourceIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    if not body.key or not body.title or not body.type:
        raise HTTPException(400, "key, title and type are required")
    if db.scalar(select(Resource.id).where(Resource.key == body.key)):
        raise HTTPException(409, "A resource with this key already exists")
    r = Resource(key=body.key, title=body.title, resource_type=body.type, status=ContentStatus.DRAFT, created_by=cu.id)
    db.add(r)
    _apply(db, r, body)
    db.commit()
    db.refresh(r)
    return admin_dict(r)


@admin.patch("/resources/{resource_id}")
def admin_update(resource_id: uuid.UUID, body: ResourceIn, db: Session = Depends(get_db)):
    r = _get(db, resource_id)
    _apply(db, r, body)
    db.commit()
    db.refresh(r)
    return admin_dict(r)


@admin.post("/resources/{resource_id}/file")
async def admin_upload(resource_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    r = _get(db, resource_id)
    limit = get_settings().resource_max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"The file is larger than {get_settings().resource_max_mb} MB")
    try:
        svc.store_file(r, file.filename or "file", data)
    except svc.ResourceError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    db.refresh(r)
    return admin_dict(r)


@admin.delete("/resources/{resource_id}/file")
def admin_remove_file(resource_id: uuid.UUID, db: Session = Depends(get_db)):
    r = _get(db, resource_id)
    if r.status == ContentStatus.PUBLISHED:
        key, r.file_key = r.file_key, ""
        problems, r.file_key = svc.readiness_problems(r), key
        if problems:
            raise HTTPException(400, "Hide the resource before removing its file: " + "; ".join(problems))
    svc.remove_file(r)
    db.commit()
    db.refresh(r)
    return admin_dict(r)


@admin.get("/resources/{resource_id}/file")
def admin_file(resource_id: uuid.UUID, db: Session = Depends(get_db)):
    """Preview a draft's file."""
    r = _get(db, resource_id)
    data = get_storage().get(r.file_key) if r.file_key else None
    if data is None:
        raise HTTPException(404, "File not found")
    return Response(data, media_type=r.content_type, headers=_file_headers(r))
