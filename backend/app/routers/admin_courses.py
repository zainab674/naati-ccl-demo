"""Courses, chapters and lessons. Admins edit every course; a teacher creates and edits their own courses, which are
shown only to that teacher's students (services/teachers.py)."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import ContentStatus, Course, CourseChapter, Lesson
from ..services import courses as outline_svc
from ..services import content_images, lesson_pdf, teachers
from ..services.html import sanitize
from ..settings import get_settings
from .admin_content import _lang, _pair

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_staff)])


def lesson_dict(lesson: Lesson, number: str | None = None) -> dict:
    return {"id": str(lesson.id), "lesson_number": lesson.lesson_number, "title": lesson.title,
            "video_url": lesson.video_url, "html_content": lesson.html_content, "is_free": lesson.is_free,
            "status": lesson.status.value, "chapter_id": str(lesson.chapter_id) if lesson.chapter_id else None,
            "number": number, "pdf": lesson_pdf.as_dict(lesson, f"/api/admin/lessons/{lesson.id}/pdf")}


def course_dict(c: Course, lessons: bool = False) -> dict:
    out = {"id": str(c.id), "key": c.key, "title": c.title, "description": c.description, "status": c.status.value,
           "is_free": c.is_free, "sort_order": c.sort_order, **_lang(c.language_pair),
           "owner": {"id": str(c.owner.id), "name": c.owner.full_name} if c.owner else None,
           "image_url": content_images.url(c, f"/api/courses/{c.id}/image"),
           "lesson_count": sum(1 for lesson in c.lessons if lesson.status != ContentStatus.ARCHIVED)}
    if lessons:
        numbers = outline_svc.display_numbers(c, published_only=False)
        out["chapters"] = [{"id": str(ch.id), "number": ch.number, "title": ch.title} for ch in c.chapters]
        # Editor order: as students read them (chapters, then loose lessons); archived lessons last.
        ordered = outline_svc.reading_order(c, published_only=False)
        rest = [lesson for lesson in c.lessons if lesson not in ordered]
        out["lessons"] = [lesson_dict(lesson, numbers.get(lesson.id)) for lesson in ordered + rest]
    return out


def _course(db: Session, course_id: uuid.UUID, cu: CurrentUser) -> Course:
    return teachers.ensure_edits_course(cu.user, db.get(Course, course_id))


def _lesson(db: Session, lesson_id: uuid.UUID, cu: CurrentUser) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    _course(db, lesson.course_id, cu)
    return lesson


def _chapter(db: Session, chapter_id: uuid.UUID, cu: CurrentUser) -> CourseChapter:
    ch = db.get(CourseChapter, chapter_id)
    if not ch:
        raise HTTPException(404, "Chapter not found")
    _course(db, ch.course_id, cu)
    return ch


@router.get("/courses")
def list_courses(cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """Admins: every course. Teachers: the courses they made."""
    query = select(Course).order_by(Course.sort_order, Course.title)
    if not cu.user.is_admin:
        query = query.where(Course.owner_id == cu.id)
    return [course_dict(c) for c in db.scalars(query)]


@router.get("/courses/{course_id}")
def get_course(course_id: uuid.UUID, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    return course_dict(_course(db, course_id, cu), lessons=True)


class CourseIn(BaseModel):
    key: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,118}$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ContentStatus | None = None
    is_free: bool | None = None
    sort_order: int | None = None
    language: str | None = None  # LOTE code; None/"" = course for every language


def _apply_course_language(db: Session, c: Course, body: CourseIn) -> None:
    if "language" in body.model_fields_set:
        c.language_pair_id = _pair(db, body.language).id if body.language else None


@router.post("/courses", status_code=201)
def create_course(body: CourseIn, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """A teacher's course belongs to them and is shown only to their students; an admin's is for every student."""
    if not body.key or not body.title:
        raise HTTPException(400, "key and title are required")
    if db.scalar(select(Course).where(Course.key == body.key)):
        raise HTTPException(409, "A course with this key already exists")
    c = Course(key=body.key, title=body.title, description=body.description or "",
               status=body.status or ContentStatus.DRAFT, is_free=bool(body.is_free), sort_order=body.sort_order or 0,
               owner_id=cu.id if cu.user.is_teacher else None)
    _apply_course_language(db, c, body)
    db.add(c)
    db.commit()
    return course_dict(c, lessons=True)


@router.patch("/courses/{course_id}")
def update_course(course_id: uuid.UUID, body: CourseIn, cu: CurrentUser = Depends(require_staff),
                  db: Session = Depends(get_db)):
    c = _course(db, course_id, cu)
    _apply_course_language(db, c, body)
    for field in body.model_fields_set - {"language"}:
        setattr(c, field, getattr(body, field))
    db.commit()
    db.refresh(c)
    return course_dict(c, lessons=True)


@router.post("/courses/{course_id}/image")
async def upload_course_image(course_id: uuid.UUID, file: UploadFile = File(...),
                              cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    c = _course(db, course_id, cu)
    try:
        content_images.store(c, "course-images", await file.read(get_settings().content_image_max_mb * 1024 * 1024 + 1))
    except content_images.ImageError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return course_dict(c, lessons=True)


@router.delete("/courses/{course_id}/image")
def remove_course_image(course_id: uuid.UUID, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    c = _course(db, course_id, cu)
    content_images.remove(c)
    db.commit()
    return course_dict(c, lessons=True)


class LessonIn(BaseModel):
    lesson_number: int | None = Field(default=None, ge=1)
    chapter_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    video_url: str | None = Field(default=None, max_length=1000)
    html_content: str | None = None
    is_free: bool | None = None
    status: ContentStatus | None = None


def _apply_lesson(db: Session, lesson: Lesson, body: LessonIn) -> None:
    if body.video_url and not body.video_url.startswith(("https://", "http://")):
        raise HTTPException(400, "Video URL must start with https://")
    if body.lesson_number is not None:
        clash = db.scalar(select(Lesson).where(Lesson.course_id == lesson.course_id,
                                               Lesson.lesson_number == body.lesson_number, Lesson.id != lesson.id))
        if clash:
            raise HTTPException(409, f"Lesson number {body.lesson_number} is already used")
    if body.chapter_id is not None:
        ch = db.get(CourseChapter, body.chapter_id)
        if not ch or ch.course_id != lesson.course_id:
            raise HTTPException(400, "That chapter belongs to another course")
    for field in body.model_fields_set:
        value = getattr(body, field)
        setattr(lesson, field, sanitize(value) if field == "html_content" else value)


@router.post("/courses/{course_id}/lessons", status_code=201)
def create_lesson(course_id: uuid.UUID, body: LessonIn, cu: CurrentUser = Depends(require_staff),
                  db: Session = Depends(get_db)):
    c = _course(db, course_id, cu)
    number = body.lesson_number or (max([lesson.lesson_number for lesson in c.lessons] or [0]) + 1)
    lesson = Lesson(course_id=c.id, lesson_number=number, title=body.title or f"Lesson {number}")
    db.add(lesson)
    db.flush()
    _apply_lesson(db, lesson, body)
    db.commit()
    return lesson_dict(lesson)


@router.patch("/lessons/{lesson_id}")
def update_lesson(lesson_id: uuid.UUID, body: LessonIn, cu: CurrentUser = Depends(require_staff),
                  db: Session = Depends(get_db)):
    lesson = _lesson(db, lesson_id, cu)
    _apply_lesson(db, lesson, body)
    db.commit()
    return lesson_dict(lesson)


@router.post("/lessons/{lesson_id}/pdf")
async def upload_lesson_pdf(lesson_id: uuid.UUID, file: UploadFile = File(...),
                            cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    lesson = _lesson(db, lesson_id, cu)
    limit = get_settings().resource_max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"The file is larger than {get_settings().resource_max_mb} MB")
    try:
        lesson_pdf.store(lesson, file.filename or "lesson.pdf", data)
    except lesson_pdf.LessonPdfError as e:
        raise HTTPException(400, str(e)) from e
    lesson.pdf_source_url = ""
    db.commit()
    return lesson_dict(lesson)


@router.delete("/lessons/{lesson_id}/pdf")
def remove_lesson_pdf(lesson_id: uuid.UUID, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    lesson = _lesson(db, lesson_id, cu)
    lesson_pdf.remove(lesson)
    db.commit()
    return lesson_dict(lesson)


@router.get("/lessons/{lesson_id}/pdf")
def admin_lesson_pdf(lesson_id: uuid.UUID, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """Editor preview, including draft lessons."""
    return lesson_pdf.response(_lesson(db, lesson_id, cu))


# ------------------------------------------------------------------ chapters

class ChapterIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    move: str | None = Field(default=None, pattern="^(up|down)$")  # reorder by swapping with a neighbour


@router.post("/courses/{course_id}/chapters", status_code=201)
def create_chapter(course_id: uuid.UUID, body: ChapterIn, cu: CurrentUser = Depends(require_staff),
                   db: Session = Depends(get_db)):
    c = _course(db, course_id, cu)
    number = max([ch.number for ch in c.chapters] or [0]) + 1
    db.add(CourseChapter(course_id=c.id, number=number, title=(body.title or f"Chapter {number}").strip()))
    db.commit()
    db.refresh(c)
    return course_dict(c, lessons=True)


@router.patch("/chapters/{chapter_id}")
def update_chapter(chapter_id: uuid.UUID, body: ChapterIn, cu: CurrentUser = Depends(require_staff),
                   db: Session = Depends(get_db)):
    ch = _chapter(db, chapter_id, cu)
    c = ch.course
    if body.title:
        ch.title = body.title.strip()
    if body.move:
        order = list(c.chapters)
        i = order.index(ch)
        j = i - 1 if body.move == "up" else i + 1
        if 0 <= j < len(order):
            other = order[j]
            # Swap numbers through a temporary value (number is unique per course).
            a, b = ch.number, other.number
            ch.number = -1
            db.flush()
            other.number = a
            db.flush()
            ch.number = b
    db.commit()
    db.refresh(c)
    return course_dict(c, lessons=True)


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: uuid.UUID, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """Removes the chapter only: its lessons stay, listed after the chapters until moved."""
    ch = _chapter(db, chapter_id, cu)
    c = ch.course
    for lesson in c.lessons:
        if lesson.chapter_id == ch.id:
            lesson.chapter_id = None
    db.delete(ch)
    db.commit()
    db.refresh(c)
    return course_dict(c, lessons=True)


class HtmlIn(BaseModel):
    html: str


@router.post("/sanitize-html")
def sanitize_preview(body: HtmlIn):
    """Editor preview: exactly what will be stored and shown to students."""
    return {"html": sanitize(body.html)}
