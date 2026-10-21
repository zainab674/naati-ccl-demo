"""Course outline: chapters in order, their lessons in order, then lessons without a chapter. The outline is the single
reading order used by the course page, the lesson sidebar and Previous / Next."""
from dataclasses import dataclass

from ..models import ContentStatus, Course, CourseChapter, Lesson


@dataclass
class Group:
    chapter: CourseChapter | None   # None: lessons not in any chapter
    lessons: list[Lesson]


def outline(c: Course, published_only: bool = True) -> list[Group]:
    def visible(lesson: Lesson) -> bool:
        return lesson.status == ContentStatus.PUBLISHED if published_only else lesson.status != ContentStatus.ARCHIVED

    lessons = [lesson for lesson in c.lessons if visible(lesson)]  # already ordered by lesson_number
    groups = [Group(ch, [lesson for lesson in lessons if lesson.chapter_id == ch.id]) for ch in c.chapters]
    if published_only:
        groups = [g for g in groups if g.lessons]
    loose = [lesson for lesson in lessons if lesson.chapter_id is None or lesson.chapter_id not in {ch.id for ch in c.chapters}]
    if loose:
        groups.append(Group(None, loose))
    return groups


def reading_order(c: Course, published_only: bool = True) -> list[Lesson]:
    return [lesson for g in outline(c, published_only) for lesson in g.lessons]


def display_numbers(c: Course, published_only: bool = True) -> dict:
    """lesson id -> "2.1" inside chapter 2, or "3" for a lesson without a chapter (counted among those lessons)."""
    out = {}
    for g in outline(c, published_only):
        for i, lesson in enumerate(g.lessons, start=1):
            out[lesson.id] = f"{g.chapter.number}.{i}" if g.chapter else str(i)
    return out
