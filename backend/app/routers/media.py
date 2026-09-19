"""Protected audio delivery.

A URL here only works if ALL of these hold:
  * signature valid and not expired (5 minutes)
  * caller is logged in, owns the attempt, and is on the same login session
    the grant was issued to (a copied URL fails in another browser/session)
  * under the per-user request rate limit
  * for the AES key: under the per-grant fetch limit
Segments are AES-128 encrypted, so .ts files are useless without the key.
"""
import re

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..auth import decode_token
from ..db import get_db
from ..models import Activity, Attempt, PlayGrant, Segment
from ..services import protection
from ..settings import get_settings

router = APIRouter(prefix="/api/media")
_FILE_RE = re.compile(r"^(index\.m3u8|key|s\d{3}\.ts)$")
NO_STORE = {"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"}


def _deny(db: Session, status: int, kind: str, detail: str, user_id: str | None, ip: str):
    protection.log_event(db, kind, detail, user_id=user_id, ip=ip)
    raise HTTPException(status, "Access denied")


@router.get("/{grant_id}/{filename}")
def media(grant_id: str, filename: str, request: Request, exp: int = 0, sig: str = "",
          ccl_session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else ""
    s = get_settings()
    if not _FILE_RE.match(filename):
        _deny(db, 404, "bad_path", filename, None, ip)

    claims = decode_token(ccl_session) if ccl_session else None
    if not claims:
        _deny(db, 401, "no_session", f"{grant_id}/{filename}", None, ip)
    uid, sid = claims["sub"], claims["sid"]

    if not protection.verify(grant_id, filename, exp, sig):
        _deny(db, 403, "bad_or_expired_signature", f"{grant_id}/{filename}", uid, ip)

    grant = db.get(PlayGrant, grant_id)
    attempt = db.get(Attempt, grant.attempt_id) if grant else None
    if not grant or not attempt or attempt.user_id != uid:
        _deny(db, 403, "wrong_owner", f"{grant_id}/{filename}", uid, ip)
    if grant.session_id != sid:
        _deny(db, 403, "session_mismatch", f"URL used from a different login session ({filename})", uid, ip)

    if protection.hit_rate_limit(f"media:{uid}", s.media_requests_per_minute):
        protection.flag_user(db, uid, f"More than {s.media_requests_per_minute} media requests/minute", ip)
        _deny(db, 429, "rate_limited", f"{filename}", uid, ip)

    seg = db.get(Segment, grant.segment_id)
    seg_dir = s.media_dir / seg.asset_key

    if filename == "index.m3u8":
        playlist = (seg_dir / "index.m3u8").read_text(encoding="utf-8")
        return Response(protection.rewrite_playlist(playlist, grant.id, exp),
                        media_type="application/vnd.apple.mpegurl", headers=NO_STORE)
    if filename == "key":
        grant.key_fetches += 1
        db.commit()
        if grant.key_fetches > s.key_fetches_per_grant:
            _deny(db, 403, "key_refetch", f"Key requested {grant.key_fetches}x for one play", uid, ip)
        return Response((seg_dir / "enc.key").read_bytes(), media_type="application/octet-stream", headers=NO_STORE)
    path = seg_dir / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="video/mp2t", headers=NO_STORE)
