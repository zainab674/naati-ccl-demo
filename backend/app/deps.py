"""Request dependencies: who is calling, and what they may open."""
import uuid
from dataclasses import dataclass

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import SubscriptionStatus, User
from .security import decode_session_token

# Subscription states that unlock paid content.
ACTIVE_PLAN_STATUSES = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}


@dataclass
class CurrentUser:
    user: User
    sid: str  # login session id (media grants are bound to it)

    @property
    def id(self) -> uuid.UUID:
        return self.user.id


def _load(db: Session, token: str | None) -> CurrentUser | None:
    claims = decode_session_token(token) if token else None
    if not claims:
        return None
    try:
        user = db.get(User, uuid.UUID(claims["sub"]))
    except (ValueError, KeyError):
        return None
    # session_version changes on password reset / logout-everywhere, which invalidates older cookies.
    if not user or not user.is_active or claims.get("ver", 0) != user.session_version:
        return None
    return CurrentUser(user, claims.get("sid", ""))


def optional_user(ccl_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> CurrentUser | None:
    return _load(db, ccl_session)


def current_user(cu: CurrentUser | None = Depends(optional_user)) -> CurrentUser:
    if not cu:
        raise HTTPException(401, "Not signed in")
    return cu


def require_admin(cu: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not cu.user.is_admin:
        raise HTTPException(403, "Admins only")
    return cu


def has_active_plan(user: User) -> bool:
    return user.is_admin or user.subscription_status in ACTIVE_PLAN_STATUSES


def requires_active_plan(cu: CurrentUser = Depends(current_user)) -> CurrentUser:
    """For routes that are paid-only with no free exceptions."""
    if not has_active_plan(cu.user):
        raise HTTPException(402, "An active plan is required")
    return cu


def ensure_access(user: User, is_free: bool) -> None:
    """For content with a free flag (intro dialogue, free lessons): free items are open to any signed-in user."""
    if not is_free and not has_active_plan(user):
        raise HTTPException(402, "An active plan is required")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""
