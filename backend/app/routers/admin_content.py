"""Admin content management: dialogues (segments, meaning units), mock tests, courses and lessons."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin
from ..jobs import enqueue
from ..models import (ContentStatus, Course, CourseChapter, Dialogue, Difficulty, LanguagePair, Lesson, MeaningUnit, MockTest,
                      MockTestDialogue, Segment, Topic)
from ..services import courses as outline_svc
from ..services import languages, media_ingest
from ..services.html import sanitize
from ..services.storage import get_storage
from ..settings import ccl_config

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _get(db: Session, model, obj_id: uuid.UUID):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


# ------------------------------------------------------------------ topics

@router.get("/topics")
def topics(db: Session = Depends(get_db)):
    return [{"id": str(t.id), "name": t.name} for t in db.scalars(select(Topic).order_by(Topic.sort_order, Topic.name))]


# ------------------------------------------------------------------ dialogues

def publish_problems(d: Dialogue) -> list[str]:
    problems = []
    active = [s for s in d.segments if s.active]
    if not active:
        problems.append("The dialogue has no active segments.")
    for s in active:
        if s.media_status != "ready":
            problems.append(f"Segment {s.segment_number}: audio is {s.media_status}.")
        if not any(m.active for m in s.meaning_units):
            problems.append(f"Segment {s.segment_number}: no active meaning units.")
    return problems


def dialogue_summary(d: Dialogue) -> dict:
    active = [s for s in d.segments if s.active]
    return {
        "id": str(d.id), "key": d.key, "title": d.title, "topic": d.topic.name if d.topic else None,
        "topic_id": str(d.topic_id) if d.topic_id else None, "difficulty": d.difficulty.value,
        "status": d.status.value, "is_free": d.is_free, "version": d.version,
        "language_pair": d.language_pair.display_name, "language": d.language_pair.lote.code,
        "language_name": d.language_pair.lote.name, "segments": len(active),
        "meaning_units": sum(1 for s in active for m in s.meaning_units if m.active),
        "media_ready": sum(1 for s in active if s.media_status == "ready"),
        "media_failed": sum(1 for s in active if s.media_status == "failed"),
        "estimated_duration": d.estimated_duration, "updated_at": d.updated_at.isoformat(),
    }


@router.get("/dialogues")
def list_dialogues(q: str = "", status: str = "", language: str = "", db: Session = Depends(get_db)):
    query = select(Dialogue).order_by(Dialogue.sort_order, Dialogue.title)
    if language:
        query = query.where(Dialogue.language_pair_id == _pair(db, language).id)
    if status:
        query = query.where(Dialogue.status == ContentStatus(status))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(func.lower(Dialogue.title).like(like) | func.lower(Dialogue.key).like(like))
    return [dialogue_summary(d) for d in db.scalars(query)]


@router.get("/dialogues/{dialogue_id}")
def get_dialogue(dialogue_id: uuid.UUID, db: Session = Depends(get_db)):
    d = _get(db, Dialogue, dialogue_id)
    return {
        **dialogue_summary(d), "description": d.description, "instructions": d.instructions,
        "maximum_score": d.maximum_score, "passing_score": d.passing_score, "sort_order": d.sort_order,
        "publish_problems": publish_problems(d),
        "segments": [{
            "id": str(s.id), "segment_number": s.segment_number, "direction": s.direction.value,
            "source_language": s.source_language.name, "target_language": s.target_language.name,
            "speaker_label": s.speaker_label, "speaker_role": s.speaker_role, "transcript": s.transcript,
            "active": s.active, "media_status": s.media_status, "media_error": s.media_error,
            "duration_seconds": s.duration_seconds, "source_audio_url": s.source_audio_url,
            "has_waveform": bool(s.waveform_image),
            "meaning_units": [{"id": str(m.id), "meaning_unit_number": m.meaning_unit_number, "meaning": m.meaning,
                               "reference_interpretation": m.reference_interpretation, "weight": m.weight,
                               "active": m.active} for m in s.meaning_units],
        } for s in d.segments],
    }


class DialogueIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    instructions: str | None = None
    topic_id: uuid.UUID | None = None
    difficulty: Difficulty | None = None
    status: ContentStatus | None = None
    is_free: bool | None = None
    maximum_score: float | None = Field(default=None, gt=0)
    passing_score: float | None = Field(default=None, ge=0)
    sort_order: int | None = None


@router.patch("/dialogues/{dialogue_id}")
def update_dialogue(dialogue_id: uuid.UUID, body: DialogueIn, db: Session = Depends(get_db)):
    d = _get(db, Dialogue, dialogue_id)
    if body.status == ContentStatus.PUBLISHED and d.status != ContentStatus.PUBLISHED:
        problems = publish_problems(d)
        if problems:
            raise HTTPException(400, "Cannot publish yet: " + " ".join(problems))
    for field in body.model_fields_set:
        setattr(d, field, getattr(body, field))
    db.commit()
    return get_dialogue(dialogue_id, db)


class SegmentIn(BaseModel):
    transcript: str | None = None
    speaker_label: str | None = None
    speaker_role: str | None = None
    active: bool | None = None


@router.patch("/segments/{segment_id}")
def update_segment(segment_id: uuid.UUID, body: SegmentIn, db: Session = Depends(get_db)):
    s = _get(db, Segment, segment_id)
    changed = False
    for field in body.model_fields_set:
        value = getattr(body, field)
        if getattr(s, field) != value:
            setattr(s, field, value)
            changed = True
    if changed:
        s.word_count = len(s.transcript.split())
        s.dialogue.version += 1
    db.commit()
    return get_dialogue(s.dialogue_id, db)


class MeaningUnitIn(BaseModel):
    id: uuid.UUID | None = None
    meaning_unit_number: int = Field(ge=1)
    meaning: str = Field(min_length=1)
    reference_interpretation: str = ""
    weight: float = Field(default=1, gt=0)
    active: bool = True


@router.put("/segments/{segment_id}/meaning-units")
def replace_meaning_units(segment_id: uuid.UUID, body: list[MeaningUnitIn], db: Session = Depends(get_db)):
    """Save the whole MU list of a segment. MUs left out are deactivated, not deleted (attempts reference them)."""
    s = _get(db, Segment, segment_id)
    numbers = [m.meaning_unit_number for m in body]
    if len(numbers) != len(set(numbers)):
        raise HTTPException(400, "Meaning unit numbers must be unique")
    existing = {m.id: m for m in s.meaning_units}
    original = {m.id: m.meaning_unit_number for m in s.meaning_units}
    unclaimed_by_number = {m.meaning_unit_number: m for m in s.meaning_units
                           if m.id not in {i.id for i in body if i.id}}
    # Park every current number out of the way so renumbering cannot hit the unique constraint.
    for m in s.meaning_units:
        m.meaning_unit_number += 100_000
    db.flush()
    kept = set()
    for item in body:
        mu = existing.get(item.id) if item.id else unclaimed_by_number.pop(item.meaning_unit_number, None)
        if mu is None:
            mu = MeaningUnit(segment_id=s.id, meaning_unit_number=item.meaning_unit_number, meaning=item.meaning)
            db.add(mu)
            s.meaning_units.append(mu)
        mu.meaning_unit_number, mu.meaning = item.meaning_unit_number, item.meaning
        mu.reference_interpretation, mu.weight, mu.active = item.reference_interpretation, item.weight, item.active
        mu.reference_language_id = s.target_language_id
        kept.add(id(mu))
    used = set(numbers)
    for mu in s.meaning_units:
        if id(mu) not in kept:
            mu.active = False
            if original.get(mu.id) not in used:
                mu.meaning_unit_number = original[mu.id]
    s.dialogue.version += 1
    db.commit()
    return get_dialogue(s.dialogue_id, db)


@router.post("/segments/{segment_id}/reprocess-media")
def reprocess_media(segment_id: uuid.UUID, db: Session = Depends(get_db)):
    s = _get(db, Segment, segment_id)
    if not s.source_audio_url:
        raise HTTPException(400, "This segment has no source audio URL")
    s.media_status, s.source_audio_hash = "pending", ""
    enqueue(db, media_ingest.JOB_KIND, {"segment_id": str(s.id)})
    db.commit()
    return {"ok": True}


@router.get("/segments/{segment_id}/waveform")
def segment_waveform(segment_id: uuid.UUID, db: Session = Depends(get_db)):
    s = _get(db, Segment, segment_id)
    data = get_storage().get(s.waveform_image) if s.waveform_image else None
    if not data:
        raise HTTPException(404, "No waveform")
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


# ------------------------------------------------------------------ mock tests

def _pair(db: Session, code: str) -> LanguagePair:
    lote = languages.lote_by_code(db, code)
    pair = languages.pair_for(db, lote) if lote else None
    if not pair:
        raise HTTPException(400, f"Unknown language '{code}'")
    return pair


def _lang(pair: LanguagePair | None) -> dict:
    return {"language": pair.lote.code if pair else None, "language_name": pair.lote.name if pair else None}


def mock_dict(m: MockTest) -> dict:
    pair = m.dialogues[0].dialogue.language_pair if m.dialogues else None
    return {"id": str(m.id), "key": m.key, "title": m.title, "status": m.status.value, "is_free": m.is_free,
            "sort_order": m.sort_order, **_lang(pair),
            "dialogues": [{"id": str(md.dialogue_id), "title": md.dialogue.title, "status": md.dialogue.status.value}
                          for md in m.dialogues]}


@router.get("/mock-tests")
def list_mock_tests(db: Session = Depends(get_db)):
    return [mock_dict(m) for m in db.scalars(select(MockTest).order_by(MockTest.sort_order, MockTest.title))]


class MockTestIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,118}$")
    title: str = Field(min_length=1, max_length=200)
    dialogue_ids: list[uuid.UUID]
    is_free: bool = False
    sort_order: int = 0
    status: ContentStatus = ContentStatus.DRAFT


def _apply_mock(db: Session, m: MockTest, body: MockTestIn) -> None:
    need = ccl_config()["mock_test"]["dialogues_per_test"]
    if len(body.dialogue_ids) != need or len(set(body.dialogue_ids)) != need:
        raise HTTPException(400, f"A mock test needs exactly {need} different dialogues")
    dialogues = [_get(db, Dialogue, i) for i in body.dialogue_ids]
    if len({d.language_pair_id for d in dialogues}) != 1:
        raise HTTPException(400, "Both dialogues must use the same language pair")
    if body.status == ContentStatus.PUBLISHED and any(d.status != ContentStatus.PUBLISHED for d in dialogues):
        raise HTTPException(400, "Publish both dialogues before publishing the mock test")
    m.key, m.title, m.is_free, m.sort_order, m.status = body.key, body.title, body.is_free, body.sort_order, body.status
    m.language_pair_id = dialogues[0].language_pair_id
    m.dialogues.clear()
    db.flush()
    for pos, d in enumerate(dialogues, start=1):
        m.dialogues.append(MockTestDialogue(dialogue_id=d.id, position=pos))


@router.post("/mock-tests", status_code=201)
def create_mock_test(body: MockTestIn, db: Session = Depends(get_db)):
    if db.scalar(select(MockTest).where(MockTest.key == body.key)):
        raise HTTPException(409, "A mock test with this key already exists")
    m = MockTest()
    db.add(m)
    _apply_mock(db, m, body)
    db.commit()
    return mock_dict(m)


@router.put("/mock-tests/{mock_id}")
def update_mock_test(mock_id: uuid.UUID, body: MockTestIn, db: Session = Depends(get_db)):
    m = _get(db, MockTest, mock_id)
    other = db.scalar(select(MockTest).where(MockTest.key == body.key, MockTest.id != m.id))
    if other:
        raise HTTPException(409, "A mock test with this key already exists")
    _apply_mock(db, m, body)
    db.commit()
    return mock_dict(m)


# ------------------------------------------------------------------ courses and lessons

def lesson_dict(lesson: Lesson, number: str | None = None) -> dict:
    return {"id": str(lesson.id), "lesson_number": lesson.lesson_number, "title": lesson.title,
            "video_url": lesson.video_url, "html_content": lesson.html_content, "is_free": lesson.is_free,
            "status": lesson.status.value, "chapter_id": str(lesson.chapter_id) if lesson.chapter_id else None,
            "number": number}


def course_dict(c: Course, lessons: bool = False) -> dict:
    out = {"id": str(c.id), "key": c.key, "title": c.title, "description": c.description, "status": c.status.value,
           "is_free": c.is_free, "sort_order": c.sort_order, **_lang(c.language_pair),
           "lesson_count": sum(1 for lesson in c.lessons if lesson.status != ContentStatus.ARCHIVED)}
    if lessons:
        numbers = outline_svc.display_numbers(c, published_only=False)
        out["chapters"] = [{"id": str(ch.id), "number": ch.number, "title": ch.title} for ch in c.chapters]
        # Editor order: as students read them (chapters, then loose lessons); archived lessons last.
        ordered = outline_svc.reading_order(c, published_only=False)
        rest = [lesson for lesson in c.lessons if lesson not in ordered]
        out["lessons"] = [lesson_dict(lesson, numbers.get(lesson.id)) for lesson in ordered + rest]
    return out


@router.get("/courses")
def list_courses(db: Session = Depends(get_db)):
    return [course_dict(c) for c in db.scalars(select(Course).order_by(Course.sort_order, Course.title))]


@router.get("/courses/{course_id}")
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)):
    return course_dict(_get(db, Course, course_id), lessons=True)


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
def create_course(body: CourseIn, db: Session = Depends(get_db)):
    if not body.key or not body.title:
        raise HTTPException(400, "key and title are required")
    if db.scalar(select(Course).where(Course.key == body.key)):
        raise HTTPException(409, "A course with this key already exists")
    c = Course(key=body.key, title=body.title, description=body.description or "",
               status=body.status or ContentStatus.DRAFT, is_free=bool(body.is_free), sort_order=body.sort_order or 0)
    _apply_course_language(db, c, body)
    db.add(c)
    db.commit()
    return course_dict(c, lessons=True)


@router.patch("/courses/{course_id}")
def update_course(course_id: uuid.UUID, body: CourseIn, db: Session = Depends(get_db)):
    c = _get(db, Course, course_id)
    _apply_course_language(db, c, body)
    for field in body.model_fields_set - {"language"}:
        setattr(c, field, getattr(body, field))
    db.commit()
    db.refresh(c)
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
def create_lesson(course_id: uuid.UUID, body: LessonIn, db: Session = Depends(get_db)):
    c = _get(db, Course, course_id)
    number = body.lesson_number or (max([lesson.lesson_number for lesson in c.lessons] or [0]) + 1)
    lesson = Lesson(course_id=c.id, lesson_number=number, title=body.title or f"Lesson {number}")
    db.add(lesson)
    db.flush()
    _apply_lesson(db, lesson, body)
    db.commit()
    return lesson_dict(lesson)


@router.patch("/lessons/{lesson_id}")
def update_lesson(lesson_id: uuid.UUID, body: LessonIn, db: Session = Depends(get_db)):
    lesson = _get(db, Lesson, lesson_id)
    _apply_lesson(db, lesson, body)
    db.commit()
    return lesson_dict(lesson)


# ------------------------------------------------------------------ chapters

class ChapterIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    move: str | None = Field(default=None, pattern="^(up|down)$")  # reorder by swapping with a neighbour


@router.post("/courses/{course_id}/chapters", status_code=201)
def create_chapter(course_id: uuid.UUID, body: ChapterIn, db: Session = Depends(get_db)):
    c = _get(db, Course, course_id)
    number = max([ch.number for ch in c.chapters] or [0]) + 1
    db.add(CourseChapter(course_id=c.id, number=number, title=(body.title or f"Chapter {number}").strip()))
    db.commit()
    db.refresh(c)
    return course_dict(c, lessons=True)


@router.patch("/chapters/{chapter_id}")
def update_chapter(chapter_id: uuid.UUID, body: ChapterIn, db: Session = Depends(get_db)):
    ch = _get(db, CourseChapter, chapter_id)
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
def delete_chapter(chapter_id: uuid.UUID, db: Session = Depends(get_db)):
    """Removes the chapter only: its lessons stay, listed after the chapters until moved."""
    ch = _get(db, CourseChapter, chapter_id)
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


@router.post("/segments/{segment_id}/suggest-meaning-units")
def suggest_meaning_units(segment_id: uuid.UUID, db: Session = Depends(get_db)):
    """AI suggestion only: the admin reviews, edits and saves. Nothing is stored here."""
    from ..services.ai import meaning_units
    from ..services.ai.llm import LLMError

    from ..services import ratelimit

    ratelimit.enforce("suggest-mus", 30)  # each call is a paid model request
    s = _get(db, Segment, segment_id)
    if not s.transcript.strip():
        raise HTTPException(400, "The segment has no transcript")
    try:
        return meaning_units.suggest(s)
    except LLMError as e:
        raise HTTPException(502, f"Suggestion failed: {e}") from e
