"""Pipeline step 1: transcribe a recorded answer and store transcript, word timestamps and the STT run."""
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from ...db import utcnow
from ...models import AIScoringRun, RunStatus, SegmentAttempt
from ...settings import get_settings
from ..storage import get_storage
from ..stt import STTError, Transcript, get_stt, normalise_audio


def mock_answer(sa: SegmentAttempt) -> str:
    """Dev without keys: pretend the student said the reference interpretation (results are labelled mock)."""
    return " ".join(m.reference_interpretation for m in sa.segment.meaning_units if m.active and m.reference_interpretation)


def transcribe_segment(db: Session, sa: SegmentAttempt, work_dir: Path | None = None) -> tuple[Transcript, Path]:
    """Returns the transcript and the normalised FLAC path (kept for timing analysis; caller removes work_dir)."""
    work = work_dir or get_settings().scratch_dir / f"score-{sa.id.hex[:12]}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True, exist_ok=True)
    raw = get_storage().get(sa.audio_user)
    if raw is None:
        raise STTError(f"Recording {sa.audio_user} is missing from storage", retryable=False)
    src = work / f"answer{Path(sa.audio_user).suffix or '.webm'}"
    src.write_bytes(raw)
    flac = normalise_audio(src, work / "answer.flac")

    target = sa.segment.target_language
    provider = get_stt(mock_answer(sa))
    run = AIScoringRun(segment_attempt_id=sa.id, source_language_id=sa.source_language_id,
                       target_language_id=sa.target_language_id, kind="stt", provider=provider.name,
                       model=get_settings().stt_model if provider.name == "groq" else "mock",
                       request_data={"language": target.stt_code or target.code, "audio_key": sa.audio_user,
                                     "bytes": len(raw)})
    db.add(run)
    try:
        t = provider.transcribe(flac, target.stt_code or None)
    except STTError as e:
        run.status, run.error_message, run.completed_at = RunStatus.FAILED, str(e)[:2000], utcnow()
        db.commit()
        raise
    run.model, run.raw_response, run.status, run.completed_at = t.model, t.raw or None, RunStatus.SUCCESS, utcnow()
    run.processed_result = {"text": t.text, "language": t.language, "confidence": t.confidence, "words": len(t.words)}
    sa.transcript_user, sa.stt_words, sa.stt_provider, sa.stt_model = t.text, t.words, t.provider, t.model
    db.commit()
    return t, flac


def cleanup(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
