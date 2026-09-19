"""Background work: transcribe + mark uploaded segments, finish attempts."""
import logging
from pathlib import Path

from ..db import SessionLocal
from ..models import Attempt, SegmentResponse
from ..settings import get_settings
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
                path = get_settings().uploads_dir / resp.audio_key
                t = transcribe(Path(path), resp.segment.target_language,
                               mock_text=resp.segment.sample_student_text)
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
