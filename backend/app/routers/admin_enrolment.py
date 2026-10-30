"""Admin: manual student enrolment (create, bulk CSV, access grants, invites, deactivate). A teacher enrols their own
students and changes only those; an admin can enrol for, or move a student to, any teacher."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import User
from ..security import hash_password
from ..services import enrolment, languages, teachers
from ..services.enrolment import EnrolmentError, NewStudent
from ..services.imports.common import MAX_CSV_BYTES

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_staff)])

MIN_PASSWORD = 8
TEMPLATE_CSV = "first_name,last_name,email,language,access,access_until,target_exam_date,note\n"
# Placeholder rows showing each option (example.com addresses; not real students).
EXAMPLE_CSV = TEMPLATE_CSV + (
    "Demo,Student,demo.student@example.com,fil,Trial,,,Demo account for testing\n"
    "Sample,Hindi,sample.hindi@example.com,hi,Active,31/12/2026,2026-11-20,Paid by bank transfer\n"
    "Sample,Free,sample.free@example.com,ar,None,,,Free content only\n")


def _student(db: Session, user_id: uuid.UUID, cu: CurrentUser) -> User:
    return teachers.ensure_manages(cu.user, db.get(User, user_id))


def _language(db: Session, code: str | None):
    if not code:
        return None
    lang = languages.lote_by_code(db, code)
    if not lang:
        raise HTTPException(400, f"Unknown language code '{code}'")
    return lang


class CreateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str = Field(max_length=255)
    language: str | None = None
    access: str = "Trial"
    access_until: date | None = None
    target_exam_date: date | None = None
    note: str = Field(default="", max_length=2000)
    password: str | None = Field(default=None, min_length=MIN_PASSWORD, max_length=200)
    send_invite: bool = True
    teacher_id: uuid.UUID | None = None  # admins only; a teacher's students are always their own


@router.post("/students", status_code=201)
def create_student(body: CreateIn, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    if not body.password and not body.send_invite:
        raise HTTPException(400, "Set a password or send an invite, otherwise the student cannot sign in")
    teacher = teachers.teacher_for(db, cu.user, body.teacher_id)
    try:
        user = enrolment.create_student(db, NewStudent(
            first_name=body.first_name, last_name=body.last_name, email=body.email, language=_language(db, body.language),
            access=body.access, access_until=body.access_until, target_exam_date=body.target_exam_date, note=body.note,
            password=body.password), cu.user, teacher)
    except EnrolmentError as e:
        raise HTTPException(409 if "already exists" in str(e) else 400, str(e)) from e
    db.commit()
    if body.send_invite:
        enrolment.send_invite(db, user)
    return {"id": str(user.id), "email": user.email}


class UpdateIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    language: str | None = None
    target_exam_date: date | None = None
    is_active: bool | None = None
    teacher_id: uuid.UUID | None = None  # admins only; None = no teacher


@router.patch("/students/{user_id}")
def update_student(user_id: uuid.UUID, body: UpdateIn, cu: CurrentUser = Depends(require_staff),
                   db: Session = Depends(get_db)):
    u = _student(db, user_id, cu)
    fields = body.model_fields_set
    if "teacher_id" in fields:
        if not cu.user.is_admin:
            raise HTTPException(403, "Only an admin can move a student to another teacher")
        t = teachers.teacher_for(db, cu.user, body.teacher_id)
        u.teacher_id = t.id if t else None
    if "first_name" in fields and body.first_name:
        u.first_name = body.first_name.strip()
    if "last_name" in fields:
        u.last_name = (body.last_name or "").strip()
    if "language" in fields:
        lang = _language(db, body.language)
        u.preferred_language_id = lang.id if lang else None
    if "target_exam_date" in fields:
        u.target_exam_date = body.target_exam_date
    if "is_active" in fields and body.is_active is not None and body.is_active != u.is_active:
        u.is_active = body.is_active
        if not body.is_active:
            u.session_version += 1  # signs the student out everywhere
    db.commit()
    return {"ok": True}


class AccessIn(BaseModel):
    access: str  # Active | Trial | None
    access_until: date | None = None
    note: str = Field(default="", max_length=2000)


@router.post("/students/{user_id}/access")
def set_access(user_id: uuid.UUID, body: AccessIn, cu: CurrentUser = Depends(require_staff),
               db: Session = Depends(get_db)):
    u = _student(db, user_id, cu)
    try:
        enrolment.grant_access(db, u, body.access, body.access_until, cu.user, body.note)
    except EnrolmentError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return {"ok": True, "stripe_managed": enrolment.stripe_managed(db, u)}


@router.post("/students/{user_id}/invite")
def resend_invite(user_id: uuid.UUID, cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    u = _student(db, user_id, cu)
    if not u.is_active:
        raise HTTPException(400, "Reactivate the account before sending an invite")
    enrolment.send_invite(db, u)
    return {"ok": True}


class PasswordIn(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/students/{user_id}/password")
def set_password(user_id: uuid.UUID, body: PasswordIn, cu: CurrentUser = Depends(require_staff),
                 db: Session = Depends(get_db)):
    """For demo/test accounts: set the password directly. Signs the student out of existing sessions."""
    u = _student(db, user_id, cu)
    u.password_hash = hash_password(body.password)
    u.session_version += 1
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ bulk

@router.get("/students-import/template")
def bulk_template():
    return Response(TEMPLATE_CSV, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="students_format.csv"'})


@router.get("/students-import/example")
def bulk_example():
    return Response(EXAMPLE_CSV, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="students_example.csv"'})


@router.post("/students-import")
async def bulk_enrol(file: UploadFile = File(...), commit: bool = Form(False), send_invites: bool = Form(True),
                     teacher_id: uuid.UUID | None = Form(None),
                     cu: CurrentUser = Depends(require_staff), db: Session = Depends(get_db)):
    """Dry run by default (commit=false): returns the validation report. With commit=true, creates the valid rows.
    Students enrolled by a teacher are that teacher's; an admin may name a teacher for the whole file."""
    teacher = teachers.teacher_for(db, cu.user, teacher_id)
    data = await file.read(MAX_CSV_BYTES + 1)
    specs, report = enrolment.parse_bulk(db, data)
    created = []
    if commit:
        if not report.ok:
            raise HTTPException(400, "Fix the errors in the file first (run the check again)")
        users = [enrolment.create_student(db, spec, cu.user, teacher) for spec in specs]
        db.commit()
        if send_invites:
            for u in users:
                enrolment.send_invite(db, u)
        created = [{"id": str(u.id), "email": u.email} for u in users]
    return {"report": report.as_dict(), "committed": commit, "created": created}
