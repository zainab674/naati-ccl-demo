"""Sign up, login, logout, password reset, profile."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import CurrentUser, client_ip, current_user, has_active_plan
from ..models import PasswordResetToken, User, UserRole
from ..security import (COOKIE_NAME, hash_password, hash_token, issue_session_token, new_reset_token,
                        verify_password)
from ..services import ratelimit
from ..services.email import send_template
from ..settings import get_settings

router = APIRouter(prefix="/api", tags=["auth"])

RESET_TOKEN_MINUTES = 60
MIN_PASSWORD = 8


def user_dict(u: User) -> dict:
    return {
        "id": str(u.id), "email": u.email, "first_name": u.first_name, "last_name": u.last_name,
        "name": u.full_name, "role": u.role.value, "subscription_status": u.subscription_status.value,
        "has_active_plan": has_active_plan(u),
        "target_exam_date": u.target_exam_date.isoformat() if u.target_exam_date else None,
    }


def _set_session(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(COOKIE_NAME, issue_session_token(user.id, user.role.value, user.session_version),
                        httponly=True, samesite="lax", secure=s.cookie_secure, max_age=s.session_hours * 3600,
                        path="/")


def _norm_email(email: str) -> str:
    return email.strip().lower()


class SignupIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)
    target_exam_date: date | None = None
    accept_terms: bool


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ratelimit.enforce(f"signup:{client_ip(request)}", 10)
    if not body.accept_terms:
        raise HTTPException(400, "Please accept the Terms and Privacy Policy")
    email = _norm_email(body.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists. Sign in or reset your password.")
    user = User(first_name=body.first_name.strip(), last_name=body.last_name.strip(), email=email,
                password_hash=hash_password(body.password), role=UserRole.STUDENT,
                target_exam_date=body.target_exam_date, last_login_at=utcnow())
    db.add(user)
    db.commit()
    _set_session(response, user)
    send_template(db, "welcome", user.email,
                  {"first_name": user.first_name, "dashboard_url": f"{get_settings().app_url}/dashboard"},
                  user_id=user.id)
    return user_dict(user)


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = _norm_email(body.email)
    ratelimit.enforce(f"login:{client_ip(request)}", 20)
    ratelimit.enforce(f"login-email:{email}", 10)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    user.last_login_at = utcnow()
    db.commit()
    _set_session(response, user)
    return user_dict(user)


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


class ForgotIn(BaseModel):
    email: str


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Always returns ok, so the endpoint cannot be used to discover which emails have accounts."""
    ratelimit.enforce(f"forgot:{client_ip(request)}", 5)
    user = db.scalar(select(User).where(User.email == _norm_email(body.email)))
    if user and user.is_active:
        token, token_hash = new_reset_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash,
                                  expires_at=utcnow() + timedelta(minutes=RESET_TOKEN_MINUTES)))
        db.commit()
        send_template(db, "password_reset", user.email, {
            "first_name": user.first_name, "expires_minutes": RESET_TOKEN_MINUTES,
            "reset_url": f"{get_settings().app_url}/reset-password?token={token}"}, user_id=user.id)
    return {"ok": True}


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ratelimit.enforce(f"reset:{client_ip(request)}", 10)
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token)))
    if not row or row.used_at or row.expires_at < utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    user = db.get(User, row.user_id)
    user.password_hash = hash_password(body.password)
    user.session_version += 1  # signs out every existing session
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id,
                                                PasswordResetToken.used_at.is_(None)).values(used_at=utcnow()))
    db.commit()
    _set_session(response, user)
    return user_dict(user)


@router.get("/me")
def me(cu: CurrentUser = Depends(current_user)):
    return user_dict(cu.user)


class MeIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    target_exam_date: date | None = None


@router.patch("/me")
def update_me(body: MeIn, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, cu.id)
    for field in body.model_fields_set:
        value = getattr(body, field)
        setattr(user, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return user_dict(user)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/me/password")
def change_password(body: PasswordIn, response: Response, cu: CurrentUser = Depends(current_user),
                    db: Session = Depends(get_db)):
    user = db.get(User, cu.id)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.session_version += 1
    db.commit()
    _set_session(response, user)
    return {"ok": True}
