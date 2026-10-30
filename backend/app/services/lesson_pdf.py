"""PDF handout per course lesson (client brief: each lesson holds a video, text and a PDF). Uploaded in the course
editor, or fetched from courses.csv pdf_url by a background job. Stored privately; served with the lesson's access."""
import logging
import shutil
import uuid
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..jobs import enqueue, handler
from ..models import Lesson
from ..settings import get_settings
from .media_ingest import DownloadError, download
from .resources import ResourceError, check_file
from .storage import get_storage

log = logging.getLogger(__name__)

FETCH_LESSON_PDF = "fetch_lesson_pdf"


class LessonPdfError(ValueError):
    pass


def store(lesson: Lesson, name: str, data: bytes) -> None:
    if not name.lower().endswith(".pdf"):
        raise LessonPdfError("The lesson handout must be a PDF file")
    try:
        clean, ctype = check_file(name, data)
    except ResourceError as e:
        raise LessonPdfError(str(e)) from e
    storage = get_storage()
    old = lesson.pdf_key
    # A new key per upload, so a student who opened the old version is not served a half-replaced file.
    lesson.pdf_key = f"lessons/{lesson.id}/{uuid.uuid4().hex}/{clean}"
    storage.put(lesson.pdf_key, data, ctype)
    lesson.pdf_name, lesson.pdf_size = clean, len(data)
    if old:
        storage.delete_prefix(old.rsplit("/", 1)[0])


def remove(lesson: Lesson) -> None:
    if lesson.pdf_key:
        get_storage().delete_prefix(lesson.pdf_key.rsplit("/", 1)[0])
    lesson.pdf_key, lesson.pdf_name, lesson.pdf_size, lesson.pdf_source_url = "", "", 0, ""


def as_dict(lesson: Lesson, url: str) -> dict | None:
    return {"name": lesson.pdf_name, "size": lesson.pdf_size, "url": url} if lesson.pdf_key else None


def response(lesson: Lesson) -> Response:
    """Inline PDF, never cached; same-origin framing only so the lesson page can embed it."""
    data = get_storage().get(lesson.pdf_key) if lesson.pdf_key else None
    if data is None:
        raise HTTPException(404, "This lesson has no PDF")
    return Response(data, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=\"{lesson.pdf_name}\"; filename*=UTF-8''{quote(lesson.pdf_name)}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN",
        "Content-Security-Policy": "frame-ancestors 'self'"})


def enqueue_fetch(db: Session, lesson: Lesson, url: str) -> None:
    enqueue(db, FETCH_LESSON_PDF, {"lesson_id": str(lesson.id), "url": url})


@handler(FETCH_LESSON_PDF)
def fetch_lesson_pdf(payload: dict) -> None:
    """Download courses.csv pdf_url into the lesson. A bad link is logged and leaves the lesson without a PDF."""
    with SessionLocal() as db:
        lesson = db.get(Lesson, uuid.UUID(payload["lesson_id"]))
        if not lesson:
            return
        work = get_settings().scratch_dir / f"lesson-pdf-{lesson.id.hex[:12]}-{uuid.uuid4().hex[:6]}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            src = work / "file.pdf"
            download(payload["url"], src)
            name = payload["url"].split("?")[0].rsplit("/", 1)[-1] or "lesson.pdf"
            store(lesson, name if name.lower().endswith(".pdf") else f"{name}.pdf", src.read_bytes())
            lesson.pdf_source_url = payload["url"]
            db.commit()
        except (DownloadError, LessonPdfError) as e:
            log.warning("lesson %s: PDF from %s not stored: %s", lesson.id, payload["url"], e)
        finally:
            shutil.rmtree(work, ignore_errors=True)
