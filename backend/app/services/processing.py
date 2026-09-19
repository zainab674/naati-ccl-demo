"""Background work: transcribe + mark uploaded segments, finish attempts."""
import logging
from pathlib import Path

from ..db import SessionLocal
from ..models import Attempt, SegmentResponse
from ..settings import get_settings
from . import storage
from .marking import MarkingError, mark_response
from .stt import transcribe

log = logging.getLogger("processing")


def process_response(response_id: str) -> None:
    db = SessionLocal()
    try:
        resp = db.get(SegmentResponse, response_id)
        if not resp:
            return
        try:
            if resp.audio_key and resp.stt_provider != "browser":
                data = storage.read(resp.audio_key, db) or b""
                tmp = get_settings().scratch_dir / f"stt-{resp.id}{Path(resp.audio_key).suffix}"
                tmp.write_bytes(data)
                try:
                    t = transcribe(tmp, resp.segment.target_language, mock_text=resp.segment.sample_student_text)
                finally:
                    tmp.unlink(missing_ok=True)
                resp.transcript, resp.stt_words_json = t.text, t.words
                resp.stt_confidence, resp.stt_provider = t.confidence, t.provider
                resp.delivery_json = {**(resp.delivery_json or {}), "detected_language": t.language}
            mark_response(db, resp)
            resp.status, resp.error = "marked", ""
        except MarkingError as e:
            resp.status, resp.error = "error", str(e)
            resp.needs_review = True
        except Exception as e:  # visible failure, never silent
            log.exception("processing failed")
            resp.status, resp.error = "error", f"{type(e).__name__}: {e}"
            resp.needs_review = True
        db.commit()
        finalize_if_done(db, resp.attempt_id)
    finally:
        db.close()


def finalize_if_done(db, attempt_id: str) -> None:
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.status not in ("marking",):
        return
    db.refresh(attempt)
    if all(r.status in ("marked", "error") for r in attempt.responses):
        attempt.status = "marked"
        db.commit()


def process_stale(db, attempt, older_than_seconds: int = 12) -> None:
    """Serverless safety net: mark any segment whose background job never ran."""
    from datetime import timedelta
    from ..models import utcnow
    cutoff = utcnow() - timedelta(seconds=older_than_seconds)
    stale = [r.id for r in attempt.responses if r.status == "uploaded" and r.created_at < cutoff]
    for rid in stale:
        process_response(rid)
    if stale:
        db.expire_all()
