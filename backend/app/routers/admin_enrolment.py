"""Admin: manual student enrolment (create, bulk CSV, access grants, invites, deactivate)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_admin
from ..models import User, UserRole
from ..security import hash_password
from ..services import enrolment, languages
from ..services.enrolment import EnrolmentError, NewStudent
from ..services.imports.common import MAX_CSV_BYTES

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

MIN_PASSWORD = 8
TEMPLATE_CSV = ("first_name,last_name,email,language,access,access_until,target_exam_date,note\n"
                "Demo,Student,demo.student@example.com,fil,Trial,,,Demo account for testing\n")


def _student(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if not u or u.role != UserRole.STUDENT:
        raise HTTPException(404, "Student not found")
    return u


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


@router.post("/students", status_code=201)
def create_student(body: CreateIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    if not body.password and not body.send_invite:
        raise HTTPException(400, "Set a password or send an invite, otherwise the student cannot sign in")
    try:
        user = enrolment.create_student(db, NewStudent(
            first_name=body.first_name, last_name=body.last_name, email=body.email, language=_language(db, body.language),
            access=body.access, access_until=body.access_until, target_exam_date=body.target_exam_date, note=body.note,
            password=body.password), cu.user)
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


@router.patch("/students/{user_id}")
def update_student(user_id: uuid.UUID, body: UpdateIn, db: Session = Depends(get_db)):
    u = _student(db, user_id)
    fields = body.model_fields_set
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
def set_access(user_id: uuid.UUID, body: AccessIn, cu: CurrentUser = Depends(require_admin),
               db: Session = Depends(get_db)):
    u = _student(db, user_id)
    try:
        enrolment.grant_access(db, u, body.access, body.access_until, cu.user, body.note)
    except EnrolmentError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return {"ok": True, "stripe_managed": enrolment.stripe_managed(db, u)}


@router.post("/students/{user_id}/invite")
def resend_invite(user_id: uuid.UUID, db: Session = Depends(get_db)):
    u = _student(db, user_id)
    if not u.is_active:
        raise HTTPException(400, "Reactivate the account before sending an invite")
    enrolment.send_invite(db, u)
    return {"ok": True}


class PasswordIn(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/students/{user_id}/password")
def set_password(user_id: uuid.UUID, body: PasswordIn, db: Session = Depends(get_db)):
    """For demo/test accounts: set the password directly. Signs the student out of existing sessions."""
    u = _student(db, user_id)
    u.password_hash = hash_password(body.password)
    u.session_version += 1
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ bulk

@router.get("/students-import/template")
def bulk_template():
    return Response(TEMPLATE_CSV, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="students_template.csv"'})


@router.post("/students-import")
async def bulk_enrol(file: UploadFile = File(...), commit: bool = Form(False), send_invites: bool = Form(True),
                     cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Dry run by default (commit=false): returns the validation report. With commit=true, creates the valid rows."""
    data = await file.read(MAX_CSV_BYTES + 1)
    specs, report = enrolment.parse_bulk(db, data)
    created = []
    if commit:
        if not report.ok:
            raise HTTPException(400, "Fix the errors in the file first (run the check again)")
        users = [enrolment.create_student(db, spec, cu.user) for spec in specs]
        db.commit()
        if send_invites:
            for u in users:
                enrolment.send_invite(db, u)
        created = [{"id": str(u.id), "email": u.email} for u in users]
    return {"report": report.as_dict(), "committed": commit, "created": created}
