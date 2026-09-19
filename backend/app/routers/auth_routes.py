from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import COOKIE_NAME, CurrentUser, current_user, issue_token, verify_password
from ..db import get_db
from ..models import User
from ..settings import ccl_config, get_settings

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    email: str
    password: str


def user_dict(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role,
            "exam_date": u.exam_date.isoformat() if u.exam_date else None, "flagged": u.flagged,
            "test_language": u.test_language}


@router.post("/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    response.set_cookie(COOKIE_NAME, issue_token(user), httponly=True, samesite="lax",
                        secure=get_settings().cookie_secure, max_age=12 * 3600, path="/")
    return user_dict(user)


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/languages")
def languages():
    return ccl_config()["languages"]


@router.get("/me")
def me(cu: CurrentUser = Depends(current_user)):
    return user_dict(cu.user)


class MeIn(BaseModel):
    exam_date: date | None = None
    test_language: str | None = None


@router.patch("/me")
def update_me(body: MeIn, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, cu.id)
    # Only update the fields the client actually sent.
    if "exam_date" in body.model_fields_set:
        user.exam_date = body.exam_date
    if "test_language" in body.model_fields_set:
        langs = {l["code"]: l for l in ccl_config()["languages"]}
        if body.test_language not in langs or not langs[body.test_language]["available"]:
            raise HTTPException(400, "That language isn't available yet")
        user.test_language = body.test_language
    db.commit()
    return user_dict(user)
