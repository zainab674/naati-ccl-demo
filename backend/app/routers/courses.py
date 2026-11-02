"""Student courses: course list, lessons (free/paid gating), completion tracking."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, ensure_access, is_locked
from ..models import ContentStatus, Course, Lesson, LessonProgress
from ..services import courses as outline_svc
from ..services import activity, content_images, languages, lesson_pdf, teachers

router = APIRouter(prefix="/api", tags=["courses"])


def _visible_lessons(c: Course) -> list[Lesson]:
    """Published lessons in reading order (chapters first, then lessons without a chapter)."""
    return outline_svc.reading_order(c)


def _lesson_free(c: Course, lesson: Lesson) -> bool:
    return c.is_free or lesson.is_free


def _done(db: Session, user_id) -> set:
    return set(db.scalars(select(LessonProgress.lesson_id).where(LessonProgress.user_id == user_id)))


def _course_or_404(db: Session, course_id: uuid.UUID, cu: CurrentUser) -> Course:
    """Published, and either a Benchmark course or one by the student's own teacher."""
    c = db.get(Course, course_id)
    if not c or c.status != ContentStatus.PUBLISHED or not teachers.sees_course(cu.user, c):
        raise HTTPException(404, "Course not found")
    return c


def _image_url(c: Course) -> str | None:
    return content_images.url(c, f"/api/courses/{c.id}/image")


def _next_lesson(lessons: list[Lesson], done: set) -> Lesson | None:
    """Where Start / Resume goes: the first lesson not finished, or the first one when all are finished."""
    return next((x for x in lessons if x.id not in done), lessons[0] if lessons else None)


@router.get("/courses")
def courses(language: str = "", cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """Courses for every language plus those for the chosen one ("" = the student's own, "all" = every course)."""
    done = _done(db, cu.id)
    out = []
    query = select(Course).where(Course.status == ContentStatus.PUBLISHED).order_by(Course.sort_order, Course.title)
    query = teachers.visible_courses(query, cu.user)
    try:
        pair = languages.student_pair(db, cu.user, language)
    except languages.LanguageRuleError as e:
        raise HTTPException(400, str(e)) from e
    if pair:
        query = query.where(or_(Course.language_pair_id.is_(None), Course.language_pair_id == pair.id))
    for c in db.scalars(query):
        lessons = _visible_lessons(c)
        nxt = _next_lesson(lessons, done)
        out.append({"id": str(c.id), "title": c.title, "description": c.description, "lessons": len(lessons),
                    "image_url": _image_url(c),
                    "next_lesson": {"id": str(nxt.id), "locked": is_locked(cu.user, _lesson_free(c, nxt))} if nxt else None,
                    "teacher": c.owner.full_name if c.owner else None,
                    "language_name": c.language_pair.lote.name if c.language_pair else None,
                    "completed": sum(1 for lesson in lessons if lesson.id in done),
                    "free_lessons": sum(1 for lesson in lessons if _lesson_free(c, lesson)),
                    "locked": all(is_locked(cu.user, _lesson_free(c, lesson)) for lesson in lessons) if lessons else False})
    return out


@router.get("/courses/{course_id}")
def course(course_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    c = _course_or_404(db, course_id, cu)
    done = _done(db, cu.id)
    numbers = outline_svc.display_numbers(c)

    def item(lesson: Lesson) -> dict:
        return {"id": str(lesson.id), "lesson_number": lesson.lesson_number, "number": numbers[lesson.id],
                "title": lesson.title, "is_free": _lesson_free(c, lesson), "locked": is_locked(cu.user, _lesson_free(c, lesson)),
                "completed": lesson.id in done, "has_video": bool(lesson.video_url)}

    groups = outline_svc.outline(c)
    return {"id": str(c.id), "title": c.title, "description": c.description, "image_url": _image_url(c),
            "chapters": [{"id": str(g.chapter.id) if g.chapter else None, "number": g.chapter.number if g.chapter else None,
                          "title": g.chapter.title if g.chapter else None, "lessons": [item(x) for x in g.lessons]}
                         for g in groups],
            "lessons": [item(x) for g in groups for x in g.lessons]}


@router.get("/courses/{course_id}/image")
def course_image(course_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """Also shown on locked courses. Drafts: only to whoever can edit the course (editor preview)."""
    c = db.get(Course, course_id)
    editor = c and (cu.user.is_admin or c.owner_id == cu.id)
    if not c or not (editor or (c.status == ContentStatus.PUBLISHED and teachers.sees_course(cu.user, c))):
        raise HTTPException(404, "Course not found")
    res = content_images.response(c)
    if res is None:
        raise HTTPException(404, "No image")
    return res


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    les = db.get(Lesson, lesson_id)
    if not les or les.status != ContentStatus.PUBLISHED:
        raise HTTPException(404, "Lesson not found")
    c = _course_or_404(db, les.course_id, cu)
    ensure_access(cu.user, _lesson_free(c, les))
    visible = _visible_lessons(c)
    idx = next(i for i, x in enumerate(visible) if x.id == les.id)
    nxt = visible[idx + 1] if idx + 1 < len(visible) else None
    prev = visible[idx - 1] if idx > 0 else None
    return {"id": str(les.id), "course_id": str(c.id), "course_title": c.title, "lesson_number": les.lesson_number,
            "number": outline_svc.display_numbers(c)[les.id],
            "chapter": {"number": les.chapter.number, "title": les.chapter.title} if les.chapter else None,
            "title": les.title, "video_url": les.video_url, "html_content": les.html_content,  # sanitised on write
            "pdf": lesson_pdf.as_dict(les, f"/api/lessons/{les.id}/pdf"),
            "completed": les.id in _done(db, cu.id),
            "next": {"id": str(nxt.id), "title": nxt.title, "locked": is_locked(cu.user, _lesson_free(c, nxt))} if nxt else None,
            "previous": {"id": str(prev.id), "title": prev.title} if prev else None}


@router.get("/lessons/{lesson_id}/pdf")
def pdf(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    lesson(lesson_id, cu, db)  # same visibility and access checks
    return lesson_pdf.response(db.get(Lesson, lesson_id))


@router.post("/lessons/{lesson_id}/complete")
def complete(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    lesson(lesson_id, cu, db)  # same visibility and access checks
    if not db.scalar(select(LessonProgress).where(LessonProgress.user_id == cu.id, LessonProgress.lesson_id == lesson_id)):
        db.add(LessonProgress(user_id=cu.id, lesson_id=lesson_id))
        les = db.get(Lesson, lesson_id)
        activity.record(db, cu.user, "lesson_completed", f"Completed lesson: {les.title}", lesson_id=lesson_id,
                        course_id=les.course_id)
        db.commit()
    return {"completed": True}


@router.delete("/lessons/{lesson_id}/complete")
def uncomplete(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(LessonProgress).where(LessonProgress.user_id == cu.id, LessonProgress.lesson_id == lesson_id))
    db.commit()
    return {"completed": False}
