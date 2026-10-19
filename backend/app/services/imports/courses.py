"""courses.csv: one row per lesson. Upserts by course_key / lesson_no; lessons missing from a re-import are archived."""
import re
from collections import OrderedDict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import ContentStatus, Course, Lesson
from ..html import sanitize
from .common import Report, parse_bool, read_csv, valid_url

REQUIRED = ["course_key", "course_title", "lesson_no", "lesson_title"]
OPTIONAL = ["course_description", "video_url", "html_content", "is_free"]
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,118}$")


@dataclass
class L:
    number: int
    title: str
    video_url: str
    html: str
    is_free: bool


@dataclass
class C:
    key: str
    title: str
    description: str
    lessons: dict[int, L] = field(default_factory=OrderedDict)


def parse(db: Session, data: bytes) -> tuple[Report, list[C]]:
    report = Report()
    rows = read_csv(data, REQUIRED, OPTIONAL)
    if rows[0].get("_unknown_columns"):
        report.warn(1, ",".join(rows[0]["_unknown_columns"]), "Unknown column(s) will be ignored")
    courses: dict[str, C] = OrderedDict()
    first_row: dict[str, dict] = {}
    seen: dict[tuple[str, int], int] = {}
    for row in rows:
        r = row["_row"]
        missing = [c for c in REQUIRED if not row.get(c)]
        for col in missing:
            report.error(r, col, "Required value is missing")
        if missing:
            continue
        key = row["course_key"].lower()
        if not KEY_RE.match(key):
            report.error(r, "course_key", "Use lowercase letters, numbers, - or _ (2-120 characters)")
            continue
        try:
            number = int(row["lesson_no"])
            if number < 1:
                raise ValueError
        except ValueError:
            report.error(r, "lesson_no", "Must be a whole number from 1")
            continue
        try:
            is_free = bool(parse_bool(row.get("is_free", "")))
        except ValueError:
            report.error(r, "is_free", "Use true/false")
            continue
        video = row.get("video_url", "")
        if video and not valid_url(video):
            report.error(r, "video_url", "Not a valid http(s) URL")
            continue
        html = sanitize(row.get("html_content", ""))
        if row.get("html_content") and len(html) < len(row["html_content"]) * 0.9:
            report.warn(r, "html_content", "Unsafe or unsupported HTML was removed")
        if key not in courses:
            courses[key] = C(key=key, title=row["course_title"], description=row.get("course_description", ""))
            first_row[key] = row
        else:
            for col in ("course_title", "course_description"):
                if row.get(col) and row.get(col) != first_row[key].get(col):
                    report.error(r, col, f"Differs from row {first_row[key]['_row']} for the same course_key")
        if (key, number) in seen:
            report.error(r, "lesson_no", f"Duplicate course_key/lesson_no (also row {seen[(key, number)]})")
            continue
        seen[(key, number)] = r
        courses[key].lessons[number] = L(number=number, title=row["lesson_title"], video_url=video, html=html,
                                         is_free=is_free)
    existing = set(db.scalars(select(Course.key).where(Course.key.in_(list(courses)))))
    report.summary = {"rows": len(rows), "courses": len(courses),
                      "new_courses": len([k for k in courses if k not in existing]),
                      "updated_courses": len([k for k in courses if k in existing]),
                      "lessons": sum(len(c.lessons) for c in courses.values())}
    return report, list(courses.values())


def commit(db: Session, courses: list[C], created_by=None) -> dict:
    counts = {"courses_created": 0, "courses_updated": 0, "lessons_created": 0, "lessons_updated": 0,
              "lessons_archived": 0}
    for c in courses:
        course = db.scalar(select(Course).where(Course.key == c.key))
        if not course:
            course = Course(key=c.key, title=c.title, description=c.description, status=ContentStatus.DRAFT)
            db.add(course)
            db.flush()
            counts["courses_created"] += 1
        elif (course.title, course.description) != (c.title, c.description):
            course.title, course.description = c.title, c.description
            counts["courses_updated"] += 1
        course.is_free = all(lesson.is_free for lesson in c.lessons.values())
        existing = {lesson.lesson_number: lesson for lesson in course.lessons}
        for item in c.lessons.values():
            lesson = existing.get(item.number)
            values = {"title": item.title, "video_url": item.video_url, "html_content": item.html,
                      "is_free": item.is_free, "status": ContentStatus.PUBLISHED}
            if not lesson:
                lesson = Lesson(course_id=course.id, lesson_number=item.number, **values)
                db.add(lesson)
                course.lessons.append(lesson)
                counts["lessons_created"] += 1
            elif any(getattr(lesson, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(lesson, k, v)
                counts["lessons_updated"] += 1
        for number, lesson in existing.items():
            if number not in c.lessons and lesson.status != ContentStatus.ARCHIVED:
                lesson.status = ContentStatus.ARCHIVED
                counts["lessons_archived"] += 1
    db.commit()
    return counts
