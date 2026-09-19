"""Signed, short-lived, session-bound media URLs + rate limiting + anomaly log."""
import hashlib
import hmac
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import PlayGrant, SecurityEvent, User, utcnow
from ..settings import get_settings

_settings = get_settings()


def sign(grant_id: str, filename: str, exp: int) -> str:
    msg = f"{grant_id}:{filename}:{exp}".encode()
    return hmac.new(_settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()[:32]


def signed_url(grant_id: str, filename: str, exp: int) -> str:
    return f"/api/media/{grant_id}/{filename}?exp={exp}&sig={sign(grant_id, filename, exp)}"


def verify(grant_id: str, filename: str, exp: int, sig: str) -> bool:
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(sign(grant_id, filename, exp), sig or "")


def new_grant(db: Session, attempt_id: str, seg_index: int, segment_id: str, session_id: str) -> tuple[PlayGrant, int]:
    ttl = _settings.signed_url_ttl_seconds
    grant = PlayGrant(
        attempt_id=attempt_id, seg_index=seg_index, segment_id=segment_id,
        session_id=session_id, expires_at=utcnow() + timedelta(seconds=ttl),
    )
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


# ---- rate limiting (in-memory sliding window; swap for Redis in production) ----
_windows: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def hit_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    now = time.time()
    with _lock:
        q = _windows[key]
        while q and q[0] < now - window_seconds:
            q.popleft()
        q.append(now)
        return len(q) > limit


def log_event(db: Session, kind: str, detail: str, user_id: str | None = None, ip: str = "") -> None:
    db.add(SecurityEvent(user_id=user_id, kind=kind, detail=detail, ip=ip))
    db.commit()


def flag_user(db: Session, user_id: str, reason: str, ip: str = "") -> None:
    user = db.get(User, user_id)
    if user and not user.flagged:
        user.flagged = True
        db.add(SecurityEvent(user_id=user_id, kind="account_flagged", detail=reason, ip=ip))
        db.commit()


def recent_denials(db: Session, minutes: int = 60) -> int:
    since = datetime.utcnow() - timedelta(minutes=minutes)
    return db.query(SecurityEvent).filter(SecurityEvent.created_at >= since).count()
