"""Attempt lifecycle for the mock test player.

A practice attempt is one DialogueAttempt; a mock test is a MockTestAttempt grouping one DialogueAttempt per
dialogue. The player addresses both by one id. Segment attempts are created up front (one per active segment) so
progress, plays and recordings are always saved server-side and a reload resumes in place.
"""
import re
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import (AttemptStatus, ContentStatus, Dialogue, DialogueAttempt, MockTest, MockTestAttempt, RepeatEvent,
                      ScoringStatus, SegmentAttempt, User)
from ..settings import ccl_config, scoring_config
from .storage import get_storage

STEPS = ("info1", "info2", "segment", "summary")
MIME_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav",
            "audio/x-wav": "wav"}


@dataclass
class AttemptRef:
    kind: str  # "mock" | "practice"
    mock: MockTestAttempt | None
    dialogue_attempts: list[DialogueAttempt]

    @property
    def id(self) -> uuid.UUID:
        return self.mock.id if self.mock else self.dialogue_attempts[0].id

    @property
    def status(self) -> AttemptStatus:
        return self.mock.status if self.mock else self.dialogue_attempts[0].status

    @property
    def step(self) -> str:
        return self.mock.current_step if self.mock else self.dialogue_attempts[0].current_step

    def set_step(self, step: str) -> None:
        if self.mock:
            self.mock.current_step = step
        else:
            self.dialogue_attempts[0].current_step = step

    @property
    def user_id(self) -> uuid.UUID:
        return self.mock.user_id if self.mock else self.dialogue_attempts[0].user_id


# ------------------------------------------------------------------ start / resume

def _new_dialogue_attempt(db: Session, user: User, dialogue: Dialogue, mock_attempt: MockTestAttempt | None = None,
                          position: int = 1) -> DialogueAttempt:
    previous = db.scalar(select(func.count()).select_from(DialogueAttempt).where(
        DialogueAttempt.user_id == user.id, DialogueAttempt.dialogue_id == dialogue.id))
    da = DialogueAttempt(id=uuid.uuid4(), user_id=user.id, dialogue_id=dialogue.id,
                         language_pair_id=dialogue.language_pair_id,
                         mock_test_attempt_id=mock_attempt.id if mock_attempt else None,
                         position=position, attempt_number=previous + 1, dialogue_version=dialogue.version,
                         maximum_score=dialogue.maximum_score, passing_score=dialogue.passing_score,
                         started_at=utcnow(), current_step="info1")
    db.add(da)
    segments = [s for s in dialogue.segments if s.active]
    if not segments or any(s.media_status != "ready" for s in segments):
        raise HTTPException(409, "This dialogue is not ready yet")
    for s in segments:
        db.add(SegmentAttempt(dialogue_attempt_id=da.id, segment_id=s.id, segment_number=s.segment_number,
                              source_language_id=s.source_language_id, target_language_id=s.target_language_id))
    return da


def start_practice(db: Session, user: User, dialogue: Dialogue) -> AttemptRef:
    existing = db.scalar(select(DialogueAttempt).where(
        DialogueAttempt.user_id == user.id, DialogueAttempt.dialogue_id == dialogue.id,
        DialogueAttempt.mock_test_attempt_id.is_(None), DialogueAttempt.status == AttemptStatus.IN_PROGRESS))
    if existing:
        return AttemptRef("practice", None, [existing])
    da = _new_dialogue_attempt(db, user, dialogue)
    db.commit()
    return AttemptRef("practice", None, [db.get(DialogueAttempt, da.id)])


def start_mock(db: Session, user: User, mock: MockTest) -> AttemptRef:
    existing = db.scalar(select(MockTestAttempt).where(
        MockTestAttempt.user_id == user.id, MockTestAttempt.mock_test_id == mock.id,
        MockTestAttempt.status == AttemptStatus.IN_PROGRESS))
    if existing:
        return AttemptRef("mock", existing, list(existing.dialogue_attempts))
    if any(md.dialogue.status != ContentStatus.PUBLISHED for md in mock.dialogues):
        raise HTTPException(409, "This mock test is not available")
    cfg = scoring_config()
    ma = MockTestAttempt(id=uuid.uuid4(), user_id=user.id, mock_test_id=mock.id, started_at=utcnow(),
                         maximum_score=sum(md.dialogue.maximum_score for md in mock.dialogues),
                         passing_score=cfg["pass_total"])
    db.add(ma)
    db.flush()
    for md in mock.dialogues:
        _new_dialogue_attempt(db, user, md.dialogue, ma, md.position)
    db.commit()
    ma = db.get(MockTestAttempt, ma.id)
    return AttemptRef("mock", ma, list(ma.dialogue_attempts))


def resolve(db: Session, attempt_id: uuid.UUID, user: User, allow_admin: bool = False) -> AttemptRef:
    ref = None
    mock = db.get(MockTestAttempt, attempt_id)
    if mock:
        ref = AttemptRef("mock", mock, list(mock.dialogue_attempts))
    else:
        da = db.get(DialogueAttempt, attempt_id)
        if da and da.mock_test_attempt_id is None:
            ref = AttemptRef("practice", None, [da])
    if not ref or (ref.user_id != user.id and not (allow_admin and user.is_admin)):
        raise HTTPException(404, "Attempt not found")
    return ref


def segment_attempt(ref: AttemptRef, segment_attempt_id: uuid.UUID) -> SegmentAttempt:
    for da in ref.dialogue_attempts:
        for sa in da.segment_attempts:
            if sa.id == segment_attempt_id:
                return sa
    raise HTTPException(404, "Segment not found")


def require_in_progress(ref: AttemptRef) -> None:
    if ref.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(409, "This attempt has been submitted")


# ------------------------------------------------------------------ state (never includes transcripts or answers)

def state(ref: AttemptRef) -> dict:
    cfg = ccl_config()
    seg_cfg = cfg["segment"]
    title = ref.mock.mock_test.title if ref.mock else ref.dialogue_attempts[0].dialogue.title
    current = None
    for da in ref.dialogue_attempts:
        for sa in da.segment_attempts:
            if not sa.audio_user and not sa.skipped:
                current = {"dialogue_attempt_id": str(da.id), "segment_attempt_id": str(sa.id)}
                break
        if current:
            break
    return {
        "id": str(ref.id), "kind": ref.kind, "title": title, "status": ref.status.value, "step": ref.step,
        "current": current,
        "config": {"max_repeats_per_dialogue": seg_cfg["max_repeats_per_dialogue"],
                   "response_window_seconds": seg_cfg["response_window_seconds"],
                   "chime_seconds": seg_cfg.get("chime_seconds", 0.6), "camera": cfg.get("camera", {}),
                   "information_1": cfg["information_1"].strip(), "information_2": cfg["information_2"].strip(),
                   "information_1_practice": cfg.get("information_1_practice", cfg["information_1"]).strip(),
                   "max_upload_mb": cfg["recording"]["max_upload_mb"]},
        "dialogues": [{
            "dialogue_attempt_id": str(da.id), "position": da.position, "title": da.dialogue.title,
            "description": da.dialogue.description, "instructions": da.dialogue.instructions,
            "topic": da.dialogue.topic.name if da.dialogue.topic else None,
            "lote": da.dialogue.language_pair.lote.name, "repeats_used": da.total_repeats,
            "segments": [{
                "segment_attempt_id": str(sa.id), "number": sa.segment_number,
                "direction": sa.segment.direction.value, "source_language": sa.segment.source_language.name,
                "target_language": sa.segment.target_language.name, "speaker_role": sa.segment.speaker_role,
                "attempts": sa.play_count, "record_count": sa.record_count, "answered": bool(sa.audio_user),
                "skipped": sa.skipped, "has_waveform": bool(sa.segment.waveform_image),
            } for sa in da.segment_attempts],
        } for da in ref.dialogue_attempts],
    }


# ------------------------------------------------------------------ playing

def register_play(db: Session, ref: AttemptRef, sa: SegmentAttempt) -> bool:
    """Start one attempt: count it server-side before any audio URL exists. Returns True when it is a repeat.

    The first Start on a segment is its attempt; every later Start (before or after Finish attempt) repeats the
    segment and uses one of the dialogue's repeats (ccl.yaml max_repeats_per_dialogue)."""
    require_in_progress(ref)
    if sa.skipped:
        raise HTTPException(409, "This segment was skipped")
    da = sa.dialogue_attempt
    is_repeat = sa.play_count > 0
    if is_repeat and da.total_repeats >= ccl_config()["segment"]["max_repeats_per_dialogue"]:
        raise HTTPException(409, "You have used the segment repeat allowed for this dialogue")
    sa.play_count += 1
    if is_repeat:
        da.total_repeats += 1
        db.add(RepeatEvent(dialogue_attempt_id=da.id, segment_attempt_id=sa.id, repeat_number=sa.play_count - 1))
    return is_repeat


# ------------------------------------------------------------------ recording upload (chunked, retry-safe)

RECORDING_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _parts_prefix(sa: SegmentAttempt, recording: str) -> str:
    """Parts live under the client's id for one take, so a late retry from a discarded take (the student pressed
    Repeat) can never overwrite a part of the take that is finally submitted."""
    if not RECORDING_ID.match(recording):
        raise HTTPException(400, "Invalid recording id")
    return f"recordings/{sa.id}/try{sa.record_count + 1}/parts/{recording}"


def save_part(ref: AttemptRef, sa: SegmentAttempt, index: int, data: bytes, recording: str = "default") -> None:
    require_in_progress(ref)
    _check_can_record(sa)
    max_bytes = ccl_config()["recording"]["max_upload_mb"] * 1024 * 1024
    if index < 0 or index > 9999 or len(data) > max_bytes:
        raise HTTPException(413, "Recording part too large")
    # Same index uploaded twice (a retry) simply overwrites: idempotent.
    get_storage().put(f"{_parts_prefix(sa, recording)}/{index:04d}", data, "application/octet-stream")


def skip(ref: AttemptRef, sa: SegmentAttempt) -> None:
    """Move on without answering. Like the real test, a skipped segment cannot be reopened."""
    require_in_progress(ref)
    if sa.audio_user:
        raise HTTPException(409, "This segment has already been answered")
    sa.skipped, sa.submitted_at = True, utcnow()
    sa.dialogue_attempt.current_segment_number = sa.segment_number + 1


def _check_can_record(sa: SegmentAttempt) -> None:
    if sa.skipped:
        raise HTTPException(409, "This segment was skipped")
    if sa.play_count < 1:
        raise HTTPException(409, "Click Start to hear the segment before recording")
    if sa.record_count >= sa.play_count:
        # One recording per attempt: a new answer needs a new Start (a repeat).
        raise HTTPException(409, "This attempt is already saved. Click Start to repeat the segment")


def complete_recording(db: Session, ref: AttemptRef, sa: SegmentAttempt, parts: int, mime: str,
                       timing: dict, duration: float | None, recording: str = "default") -> None:
    require_in_progress(ref)
    _check_can_record(sa)
    rec_cfg = ccl_config()["recording"]
    mime = (mime or "audio/webm").split(";")[0].strip().lower()
    if mime not in rec_cfg["allowed_mime_types"]:
        raise HTTPException(415, f"Unsupported audio type {mime}")
    storage = get_storage()
    prefix = _parts_prefix(sa, recording)
    chunks = []
    for i in range(parts):
        chunk = storage.get(f"{prefix}/{i:04d}")
        if chunk is None:
            raise HTTPException(409, f"Recording part {i} is missing; upload it again")
        chunks.append(chunk)
    data = b"".join(chunks)
    if len(data) > rec_cfg["max_upload_mb"] * 1024 * 1024:
        raise HTTPException(413, "Recording too large")
    sa.record_count += 1
    key = f"recordings/{sa.id}/try{sa.record_count}.{MIME_EXT.get(mime, 'webm')}"
    storage.put(key, data, mime)
    if sa.audio_user and sa.audio_user != key:
        storage.delete(sa.audio_user)  # only the last attempt is kept and scored
    storage.delete_prefix(prefix.rsplit("/parts/", 1)[0] + "/parts")  # this take and any discarded ones
    sa.audio_user, sa.audio_mime, sa.submitted_at, sa.skipped = key, mime, utcnow(), False
    sa.audio_duration_seconds = duration
    # Client clock values (ms since epoch) only; the delay itself is measured from the audio in scoring.
    sa.timing = {k: timing.get(k) for k in ("chime_end_ms", "record_start_ms", "record_stop_ms", "speech_start_ms")
                 if isinstance(timing.get(k), int | float)}
    da = sa.dialogue_attempt
    da.current_segment_number = sa.segment_number + 1


# ------------------------------------------------------------------ submit

def submit(db: Session, ref: AttemptRef) -> None:
    require_in_progress(ref)
    now = utcnow()
    for da in ref.dialogue_attempts:
        for sa in da.segment_attempts:
            if not sa.audio_user:
                sa.skipped = True
                sa.submitted_at = now
            sa.scoring_status = ScoringStatus.PENDING
        da.status, da.submitted_at, da.scoring_status = AttemptStatus.COMPLETED, now, ScoringStatus.PENDING
        da.current_step = "summary"
    if ref.mock:
        ref.mock.status, ref.mock.submitted_at = AttemptStatus.COMPLETED, now
        ref.mock.scoring_status, ref.mock.current_step = ScoringStatus.PENDING, "summary"
    from .scoring_jobs import enqueue_attempt  # scoring runs in the worker
    enqueue_attempt(db, ref)
