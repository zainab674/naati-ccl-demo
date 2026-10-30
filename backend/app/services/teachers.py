"""Teachers and their students. Admins reach every student and course; a teacher reaches only students whose
teacher_id is theirs (enrolled by them, joined through their link, or assigned by an admin) and courses they own."""
import secrets

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Course, User, UserRole

JOIN_CODE_BYTES = 6  # 8 url-safe characters


def manages(staff: User, student: User) -> bool:
    return staff.is_admin or (staff.is_teacher and student.teacher_id == staff.id)


def ensure_manages(staff: User, student: User | None) -> User:
    """404 (not 403) so a teacher cannot tell whether another teacher's student exists."""
    if not student or student.role != UserRole.STUDENT or not manages(staff, student):
        raise HTTPException(404, "Student not found")
    return student


def scope_students(query, staff: User):
    """Narrow a select over User to the students this staff member manages."""
    return query.where(User.teacher_id == staff.id) if not staff.is_admin else query


def scope_by_student(query, staff: User, user_id_column):
    """Narrow a select over rows that belong to a student (attempts, segments) to this staff member's students."""
    if staff.is_admin:
        return query
    return query.where(user_id_column.in_(select(User.id).where(User.teacher_id == staff.id)))


def teacher_for(db: Session, staff: User, teacher_id=None) -> User | None:
    """The teacher a newly enrolled student gets: a teacher enrolling gets them; an admin may name one."""
    if staff.is_teacher:
        return staff
    if not teacher_id:
        return None
    t = db.get(User, teacher_id)
    if not t or t.role != UserRole.TEACHER:
        raise HTTPException(400, "That teacher was not found")
    return t


def join_code(db: Session, teacher: User, regenerate: bool = False) -> str:
    if regenerate or not teacher.join_code:
        while True:
            code = secrets.token_urlsafe(JOIN_CODE_BYTES)
            if not db.scalar(select(User.id).where(User.join_code == code)):
                break
        teacher.join_code = code
        db.commit()
    return teacher.join_code


def by_join_code(db: Session, code: str | None) -> User | None:
    """An active teacher's join code, or None (unknown, regenerated, or the teacher was removed or deactivated)."""
    if not code:
        return None
    t = db.scalar(select(User).where(User.join_code == code))
    return t if t and t.role == UserRole.TEACHER and t.is_active else None


# ------------------------------------------------------------------ courses

def ensure_edits_course(staff: User, course: Course | None) -> Course:
    if not course or not (staff.is_admin or course.owner_id == staff.id):
        raise HTTPException(404, "Course not found")
    return course


def _course_owner_for(user: User):
    """Whose courses a user sees besides Benchmark's: a student their teacher's, a teacher their own."""
    return user.id if user.is_teacher else user.teacher_id


def visible_courses(query, user: User):
    """Benchmark courses (no owner) for everyone, plus the student's teacher's (or the teacher's own) courses."""
    if user.is_admin:
        return query
    owner = _course_owner_for(user)
    return query.where(or_(Course.owner_id.is_(None), Course.owner_id == owner) if owner else Course.owner_id.is_(None))


def sees_course(user: User, course: Course) -> bool:
    return user.is_admin or course.owner_id is None or course.owner_id == _course_owner_for(user)
