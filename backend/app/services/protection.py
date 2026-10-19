"""Content protection (from the demo): signed, short-lived, session-bound media URLs, rate limiting, anomaly log."""
import hashlib
import hmac
import time
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import PlayGrant, SecurityEvent, User
from ..settings import get_settings


def sign(grant_id: str, filename: str, exp: int) -> str:
    msg = f"{grant_id}:{filename}:{exp}".encode()
    return hmac.new(get_settings().secret_key.encode(), msg, hashlib.sha256).hexdigest()[:32]


def signed_url(grant_id: str, filename: str, exp: int) -> str:
    return f"/api/media/{grant_id}/{filename}?exp={exp}&sig={sign(grant_id, filename, exp)}"


def verify(grant_id: str, filename: str, exp: int, sig: str) -> bool:
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(sign(grant_id, filename, exp), sig or "")


def new_grant(db: Session, segment_attempt_id: uuid.UUID, user_id: uuid.UUID, session_id: str) -> tuple[PlayGrant, int]:
    ttl = get_settings().signed_url_ttl_seconds
    grant = PlayGrant(id=uuid.uuid4(), segment_attempt_id=segment_attempt_id, user_id=user_id, session_id=session_id,
                      expires_at=utcnow() + timedelta(seconds=ttl))
    db.add(grant)
    db.flush()
    return grant, int(time.time()) + ttl


def rewrite_playlist(playlist: str, grant_id: str, exp: int) -> str:
    """Point every segment and the AES key at signed URLs for this grant only."""
    out = []
    for line in playlist.splitlines():
        if line.startswith("#EXT-X-KEY"):
            line = line.replace("__KEY_URI__", signed_url(grant_id, "key", exp))
        elif line and not line.startswith("#"):
            line = signed_url(grant_id, line.strip(), exp)
        out.append(line)
    return "\n".join(out) + "\n"


def log_event(db: Session, kind: str, detail: str, user_id=None, ip: str = "") -> None:
    db.add(SecurityEvent(user_id=user_id, kind=kind, detail=detail[:2000], ip=ip))
    db.commit()


def flag_user(db: Session, user_id, reason: str, ip: str = "") -> None:
    user = db.get(User, user_id)
    if user and not user.flagged:
        user.flagged = True
        db.add(SecurityEvent(user_id=user_id, kind="account_flagged", detail=reason, ip=ip))
        db.commit()
