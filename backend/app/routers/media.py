"""Protected audio delivery (from the demo).

A URL here only works if ALL of these hold:
  * signature valid and not expired
  * caller is logged in, owns the attempt, and is on the same login session the grant was issued to
    (a copied URL fails in another browser/session)
  * under the per-user request rate limit
  * for the AES key: under the per-grant fetch limit
Segments are AES-128 encrypted, so .ts files are useless without the key.
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, client_ip, optional_user
from ..models import PlayGrant, SegmentAttempt
from ..services import protection, ratelimit
from ..services.storage import get_storage
from ..settings import get_settings

router = APIRouter(prefix="/api/media", tags=["media"])
_FILE_RE = re.compile(r"^(index\.m3u8|key|s\d{3}\.ts)$")
NO_STORE = {"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"}


def _deny(db: Session, status: int, kind: str, detail: str, user_id, ip: str):
    protection.log_event(db, kind, detail, user_id=user_id, ip=ip)
    raise HTTPException(status, "Access denied")


@router.get("/{grant_id}/{filename}")
def media(grant_id: str, filename: str, request: Request, exp: int = 0, sig: str = "",
          cu: CurrentUser | None = Depends(optional_user), db: Session = Depends(get_db)):
    ip = client_ip(request)
    s = get_settings()
    if not _FILE_RE.match(filename):
        _deny(db, 404, "bad_path", filename, None, ip)
    if not cu:
        _deny(db, 401, "no_session", f"{grant_id}/{filename}", None, ip)
    if not protection.verify(grant_id, filename, exp, sig):
        _deny(db, 403, "bad_or_expired_signature", f"{grant_id}/{filename}", cu.id, ip)
    try:
        grant = db.get(PlayGrant, uuid.UUID(grant_id))
    except ValueError:
        grant = None
    if not grant or grant.user_id != cu.id:
        _deny(db, 403, "wrong_owner", f"{grant_id}/{filename}", cu.id, ip)
    if grant.session_id != cu.sid:
        _deny(db, 403, "session_mismatch", f"URL used from a different login session ({filename})", cu.id, ip)
    if ratelimit.hit(f"media:{cu.id}", s.media_requests_per_minute):
        protection.flag_user(db, cu.id, f"More than {s.media_requests_per_minute} media requests/minute", ip)
        _deny(db, 429, "rate_limited", filename, cu.id, ip)

    seg_attempt = db.get(SegmentAttempt, grant.segment_attempt_id)
    base = seg_attempt.segment.audio_file
    storage = get_storage()
    if filename == "index.m3u8":
        playlist = (storage.get(f"{base}/index.m3u8") or b"").decode("utf-8")
        return Response(protection.rewrite_playlist(playlist, str(grant.id), exp),
                        media_type="application/vnd.apple.mpegurl", headers=NO_STORE)
    if filename == "key":
        grant.key_fetches += 1
        db.commit()
        if grant.key_fetches > s.key_fetches_per_grant:
            _deny(db, 403, "key_refetch", f"Key requested {grant.key_fetches}x for one play", cu.id, ip)
        return Response(storage.get(f"{base}/enc.key"), media_type="application/octet-stream", headers=NO_STORE)
    data = storage.get(f"{base}/{filename}")
    if data is None:
        raise HTTPException(404, "Not found")
    return Response(data, media_type="video/mp2t", headers=NO_STORE)
