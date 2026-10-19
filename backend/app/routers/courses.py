"""Student courses: course list, lessons (free/paid gating), completion tracking."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, ensure_access, is_locked
from ..models import ContentStatus, Course, Lesson, LessonProgress

router = APIRouter(prefix="/api", tags=["courses"])


def _visible_lessons(c: Course) -> list[Lesson]:
    return [lesson for lesson in c.lessons if lesson.status == ContentStatus.PUBLISHED]


def _lesson_free(c: Course, lesson: Lesson) -> bool:
    return c.is_free or lesson.is_free


def _done(db: Session, user_id) -> set:
    return set(db.scalars(select(LessonProgress.lesson_id).where(LessonProgress.user_id == user_id)))


def _course_or_404(db: Session, course_id: uuid.UUID) -> Course:
    c = db.get(Course, course_id)
    if not c or c.status != ContentStatus.PUBLISHED:
        raise HTTPException(404, "Course not found")
    return c


@router.get("/courses")
def courses(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    done = _done(db, cu.id)
    out = []
    for c in db.scalars(select(Course).where(Course.status == ContentStatus.PUBLISHED).order_by(Course.sort_order, Course.title)):
        lessons = _visible_lessons(c)
        out.append({"id": str(c.id), "title": c.title, "description": c.description, "lessons": len(lessons),
                    "completed": sum(1 for lesson in lessons if lesson.id in done),
                    "free_lessons": sum(1 for lesson in lessons if _lesson_free(c, lesson)),
                    "locked": all(is_locked(cu.user, _lesson_free(c, lesson)) for lesson in lessons) if lessons else False})
    return out


@router.get("/courses/{course_id}")
def course(course_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    c = _course_or_404(db, course_id)
    done = _done(db, cu.id)
    return {"id": str(c.id), "title": c.title, "description": c.description,
            "lessons": [{"id": str(lesson.id), "lesson_number": lesson.lesson_number, "title": lesson.title,
                         "is_free": _lesson_free(c, lesson), "locked": is_locked(cu.user, _lesson_free(c, lesson)),
                         "completed": lesson.id in done, "has_video": bool(lesson.video_url)}
                        for lesson in _visible_lessons(c)]}


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    les = db.get(Lesson, lesson_id)
    if not les or les.status != ContentStatus.PUBLISHED:
        raise HTTPException(404, "Lesson not found")
    c = _course_or_404(db, les.course_id)
    ensure_access(cu.user, _lesson_free(c, les))
    visible = _visible_lessons(c)
    idx = next(i for i, x in enumerate(visible) if x.id == les.id)
    nxt = visible[idx + 1] if idx + 1 < len(visible) else None
    prev = visible[idx - 1] if idx > 0 else None
    return {"id": str(les.id), "course_id": str(c.id), "course_title": c.title, "lesson_number": les.lesson_number,
            "title": les.title, "video_url": les.video_url, "html_content": les.html_content,  # sanitised on write
            "completed": les.id in _done(db, cu.id),
            "next": {"id": str(nxt.id), "title": nxt.title, "locked": is_locked(cu.user, _lesson_free(c, nxt))} if nxt else None,
            "previous": {"id": str(prev.id), "title": prev.title} if prev else None}


@router.post("/lessons/{lesson_id}/complete")
def complete(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    lesson(lesson_id, cu, db)  # same visibility and access checks
    if not db.scalar(select(LessonProgress).where(LessonProgress.user_id == cu.id, LessonProgress.lesson_id == lesson_id)):
        db.add(LessonProgress(user_id=cu.id, lesson_id=lesson_id))
        db.commit()
    return {"completed": True}


@router.delete("/lessons/{lesson_id}/complete")
def uncomplete(lesson_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(LessonProgress).where(LessonProgress.user_id == cu.id, LessonProgress.lesson_id == lesson_id))
    db.commit()
    return {"completed": False}
