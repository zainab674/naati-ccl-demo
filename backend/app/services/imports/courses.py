"""courses.csv: one row per lesson. Upserts by course_key / lesson_no; lessons missing from a re-import are archived.
Optional chapter_no / chapter_title group lessons into chapters (upserted by number; a course whose rows give chapters
loses chapters the file no longer mentions, and their lessons become chapterless)."""
import re
from collections import OrderedDict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import ContentStatus, Course, CourseChapter, Lesson
from .. import lesson_pdf
from ..html import sanitize
from ..languages import english, get_or_create_pair, lotes_by_code
from .common import MAX_NUMBER, Report, check_lengths, parse_bool, read_csv, valid_url

REQUIRED = ["course_key", "course_title", "lesson_no", "lesson_title"]
OPTIONAL = ["course_description", "video_url", "html_content", "is_free", "lote_language", "chapter_no", "chapter_title",
            "pdf_url", "course_at_a_glance", "lesson_notes", "duration_minutes"]
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,118}$")
LENGTHS = {"course_title": Course.__table__.c.title.type.length, "lesson_title": Lesson.__table__.c.title.type.length,
           "chapter_title": CourseChapter.__table__.c.title.type.length,
           "video_url": Lesson.__table__.c.video_url.type.length}


@dataclass
class L:
    number: int
    title: str
    video_url: str  # empty leaves what staff entered, like html, is_free, notes and duration
    html: str
    is_free: bool | None
    chapter: int | None = None
    pdf_url: str = ""  # fetched into the lesson by a job on commit; empty leaves an uploaded PDF in place
    notes: str = ""
    duration: int | None = None


@dataclass
class C:
    key: str
    title: str
    description: str
    lote: str = ""  # language code; empty = course for every language
    at_a_glance: str = ""
    lessons: dict[int, L] = field(default_factory=OrderedDict)
    chapters: dict[int, str] = field(default_factory=dict)  # chapter number -> title


def parse(db: Session, data: bytes) -> tuple[Report, list[C]]:
    report = Report()
    rows = read_csv(data, REQUIRED, OPTIONAL)
    if rows[0].get("_unknown_columns"):
        report.warn(1, ",".join(rows[0]["_unknown_columns"]), "Unknown column(s) will be ignored")
    courses: dict[str, C] = OrderedDict()
    lotes = lotes_by_code(db)
    first_row: dict[str, dict] = {}
    seen: dict[tuple[str, int], int] = {}
    for row in rows:
        r = row["_row"]
        missing = [c for c in REQUIRED if not row.get(c)]
        for col in missing:
            report.error(r, col, "Required value is missing")
        if missing or not check_lengths(report, row, LENGTHS):
            continue
        key = row["course_key"].lower()
        if not KEY_RE.match(key):
            report.error(r, "course_key", "Use lowercase letters, numbers, - or _ (2-120 characters)")
            continue
        try:
            number = int(row["lesson_no"])
            if not 1 <= number <= MAX_NUMBER:
                raise ValueError
        except ValueError:
            report.error(r, "lesson_no", f"Must be a whole number from 1 to {MAX_NUMBER}")
            continue
        try:
            is_free = parse_bool(row.get("is_free", ""))
        except ValueError:
            report.error(r, "is_free", "Use true/false")
            continue
        video = row.get("video_url", "")
        if video and not valid_url(video):
            report.error(r, "video_url", "Not a valid http(s) URL")
            continue
        pdf_url = row.get("pdf_url", "")
        if pdf_url and not valid_url(pdf_url):
            report.error(r, "pdf_url", "Not a valid http(s) URL")
            continue
        lote = row.get("lote_language", "").lower()
        if lote and lote not in lotes:
            report.error(r, "lote_language", f"Unknown language code '{lote}' (use one of: {', '.join(sorted(lotes))})")
            continue
        chapter = None
        if row.get("chapter_no"):
            try:
                chapter = int(row["chapter_no"])
                if not 1 <= chapter <= MAX_NUMBER:
                    raise ValueError
            except ValueError:
                report.error(r, "chapter_no", f"Must be a whole number from 1 to {MAX_NUMBER}")
                continue
        elif row.get("chapter_title"):
            report.error(r, "chapter_no", "Give a chapter number with the chapter title")
            continue
        duration = None
        if row.get("duration_minutes"):
            try:
                duration = int(row["duration_minutes"])
                if not 1 <= duration <= 6000:
                    raise ValueError
            except ValueError:
                report.error(r, "duration_minutes", "Must be a whole number of minutes from 1 to 6000")
                continue
        cleaned = {}
        for col in ("html_content", "lesson_notes", "course_at_a_glance"):
            cleaned[col] = sanitize(row.get(col, ""))
            if row.get(col) and len(cleaned[col]) < len(row[col]) * 0.9:
                report.warn(r, col, "Unsafe or unsupported HTML was removed")
        if key not in courses:
            courses[key] = C(key=key, title=row["course_title"], description=row.get("course_description", ""), lote=lote,
                             at_a_glance=cleaned["course_at_a_glance"])
            first_row[key] = row
        else:
            for col in ("course_title", "course_description", "lote_language", "course_at_a_glance"):
                if row.get(col) and row.get(col) != first_row[key].get(col):
                    report.error(r, col, f"Differs from row {first_row[key]['_row']} for the same course_key")
        if (key, number) in seen:
            report.error(r, "lesson_no", f"Duplicate course_key/lesson_no (also row {seen[(key, number)]})")
            continue
        seen[(key, number)] = r
        if chapter is not None:
            title = row.get("chapter_title", "")
            known = courses[key].chapters.get(chapter)
            if known is None:
                if not title:
                    report.error(r, "chapter_title", f"Give a title for chapter {chapter} (on its first row)")
                    continue
                courses[key].chapters[chapter] = title
            elif title and title != known:
                report.error(r, "chapter_title", f"Chapter {chapter} is already called '{known}'")
                continue
        courses[key].lessons[number] = L(number=number, title=row["lesson_title"], video_url=video,
                                         html=cleaned["html_content"], is_free=is_free, chapter=chapter, pdf_url=pdf_url,
                                         notes=cleaned["lesson_notes"], duration=duration)
    for key, course in courses.items():
        archived = db.scalars(select(Lesson.lesson_number).join(Course).where(
            Course.key == key, Lesson.status == ContentStatus.ARCHIVED, Lesson.lesson_number.in_(list(course.lessons))))
        for number in archived:
            report.warn(None, "lesson_no", f"{key}: lesson {number} is archived and stays hidden; publish it in the "
                                           "course editor to show it again")
    existing = set(db.scalars(select(Course.key).where(Course.key.in_(list(courses)))))
    report.summary = {"rows": len(rows), "courses": len(courses),
                      "new_courses": len([k for k in courses if k not in existing]),
                      "updated_courses": len([k for k in courses if k in existing]),
                      "lessons": sum(len(c.lessons) for c in courses.values()),
                      "chapters": sum(len(c.chapters) for c in courses.values())}
    return report, list(courses.values())


def commit(db: Session, courses: list[C], created_by=None) -> dict:
    counts = {"courses_created": 0, "courses_updated": 0, "lessons_created": 0, "lessons_updated": 0,
              "lessons_archived": 0, "pdfs_queued": 0}
    fetch: list[tuple[Lesson, str]] = []
    lotes = lotes_by_code(db)
    for c in courses:
        pair_id = get_or_create_pair(db, english(db), lotes[c.lote]).id if c.lote else None
        course = db.scalar(select(Course).where(Course.key == c.key))
        if not course:
            course = Course(key=c.key, title=c.title, description=c.description, status=ContentStatus.DRAFT)
            db.add(course)
            db.flush()
            counts["courses_created"] += 1
        elif (course.title, course.description) != (c.title, c.description):
            course.title, course.description = c.title, c.description
            counts["courses_updated"] += 1
        if c.at_a_glance:
            course.at_a_glance_html = c.at_a_glance
        course.language_pair_id = pair_id
        chapter_ids = {}
        if c.chapters:
            by_number = {ch.number: ch for ch in course.chapters}
            for n, title in c.chapters.items():
                ch = by_number.get(n)
                if not ch:
                    ch = CourseChapter(course_id=course.id, number=n, title=title)
                    db.add(ch)
                    course.chapters.append(ch)
                ch.title = title
                db.flush()
                chapter_ids[n] = ch.id
            for n, ch in by_number.items():
                if n not in c.chapters:
                    for lesson in course.lessons:
                        if lesson.chapter_id == ch.id:
                            lesson.chapter_id = None
                    db.delete(ch)
        existing = {lesson.lesson_number: lesson for lesson in course.lessons}
        for item in c.lessons.values():
            lesson = existing.get(item.number)
            values = {"title": item.title}
            if item.video_url or not lesson:
                values["video_url"] = item.video_url
            if item.html or not lesson:
                values["html_content"] = item.html
            if item.is_free is not None or not lesson:
                values["is_free"] = bool(item.is_free)
            if not lesson:
                values["status"] = ContentStatus.PUBLISHED
            if c.chapters:  # files without chapter columns leave chapters as the admin set them
                values["chapter_id"] = chapter_ids.get(item.chapter)
            if item.notes:
                values["notes_html"] = item.notes
            if item.duration:
                values["duration_minutes"] = item.duration
            if not lesson:
                lesson = Lesson(course_id=course.id, lesson_number=item.number, **values)
                db.add(lesson)
                course.lessons.append(lesson)
                counts["lessons_created"] += 1
            elif any(getattr(lesson, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(lesson, k, v)
                counts["lessons_updated"] += 1
            if item.pdf_url and item.pdf_url != lesson.pdf_source_url:
                fetch.append((lesson, item.pdf_url))
        for number, lesson in existing.items():
            if number not in c.lessons and lesson.status != ContentStatus.ARCHIVED:
                lesson.status = ContentStatus.ARCHIVED
                counts["lessons_archived"] += 1
        shown = [lesson for lesson in course.lessons if lesson.status != ContentStatus.ARCHIVED]
        course.is_free = bool(shown) and all(lesson.is_free for lesson in shown)
    db.flush()
    for lesson, url in fetch:  # a re-import with the same pdf_url does not download it again
        lesson_pdf.enqueue_fetch(db, lesson, url)
    counts["pdfs_queued"] = len(fetch)
    db.commit()
    return counts
