"""Admin: the team (admins and teachers). Admins only; teachers cannot add staff or change roles."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_admin
from ..models import User, UserRole
from ..security import hash_password
from ..services import enrolment
from ..services.enrolment import EnrolmentError

router = APIRouter(prefix="/api/admin/team", tags=["admin"], dependencies=[Depends(require_admin)])

STAFF_ROLES = (UserRole.ADMIN, UserRole.TEACHER)


def _role(value: str) -> UserRole:
    try:
        return UserRole(value)
    except ValueError:
        raise HTTPException(400, "Role must be student, teacher or admin") from None


def _row(u: User) -> dict:
    return {"id": str(u.id), "name": u.full_name, "email": u.email, "role": u.role.value, "is_active": u.is_active,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat()}


@router.get("")
def team(db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.role, User.first_name)).all()
    return [_row(u) for u in users]


class CreateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str = Field(max_length=255)
    role: str = "teacher"


@router.post("", status_code=201)
def add_member(body: CreateIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Creates the account (or promotes an existing student) and emails a set-password invite to new accounts."""
    role = _role(body.role)
    if role not in STAFF_ROLES:
        raise HTTPException(400, "Role must be teacher or admin")
    try:
        email = enrolment.normalise_email(body.email)
    except EnrolmentError as e:
        raise HTTPException(400, str(e)) from e
    user = db.scalar(select(User).where(User.email == email))
    if user and user.role in STAFF_ROLES:
        raise HTTPException(409, f"{email} is already on the team")
    invite = user is None
    if invite:
        user = User(first_name=body.first_name.strip(), last_name=body.last_name.strip(), email=email,
                    password_hash=hash_password(secrets.token_urlsafe(32)), enrolled_by_id=cu.user.id)
        db.add(user)
    user.role = role
    db.commit()
    if invite:
        enrolment.send_invite(db, user)
    return {**_row(user), "invited": invite}


class UpdateIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.patch("/{user_id}")
def update_member(user_id: uuid.UUID, body: UpdateIn, cu: CurrentUser = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """Change a team member's role (student removes them from the team) or deactivate them."""
    u = db.get(User, user_id)
    if not u or u.role not in STAFF_ROLES:
        raise HTTPException(404, "Team member not found")
    if u.id == cu.user.id:
        raise HTTPException(400, "You cannot change your own role or deactivate yourself")
    if body.role is not None:
        u.role = _role(body.role)  # takes effect on their next request (the role is read from the database)
    if body.is_active is not None and body.is_active != u.is_active:
        u.is_active = body.is_active
        if not body.is_active:
            u.session_version += 1
    db.commit()
    return _row(u)
