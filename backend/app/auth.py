import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .settings import get_settings

COOKIE_NAME = "ccl_session"
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return hmac.compare_digest(check, digest)


def issue_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "role": user.role,
        "sid": secrets.token_hex(12),  # login session id; media grants are bound to it
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


class CurrentUser:
    def __init__(self, user: User, sid: str):
        self.user = user
        self.sid = sid

    @property
    def id(self) -> str:
        return self.user.id


def current_user(
    ccl_session: str | None = Cookie(default=None), db: Session = Depends(get_db)
) -> CurrentUser:
    claims = decode_token(ccl_session) if ccl_session else None
    if not claims:
        raise HTTPException(401, "Not signed in")
    user = db.get(User, claims["sub"])
    if not user:
        raise HTTPException(401, "Not signed in")
    return CurrentUser(user, claims["sid"])


def assessor_user(cu: CurrentUser = Depends(current_user)) -> CurrentUser:
    if cu.user.role != "assessor":
        raise HTTPException(403, "Assessor only")
    return cu
