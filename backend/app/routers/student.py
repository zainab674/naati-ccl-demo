"""Student API: dashboard, dialogue library, mock tests, the test player, recordings."""
import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import CurrentUser, current_user, ensure_access, has_active_plan, is_locked
from ..models import (AttemptStatus, ContentStatus, Dialogue, DialogueAttempt, MockTest, MockTestAttempt, RecordStatus,
                      ScoringStatus, Topic)
from ..services import attempts as svc
from ..services import protection, ratelimit
from ..services.storage import get_storage
from ..settings import ccl_config, get_settings, scoring_config

router = APIRouter(prefix="/api", tags=["student"])


# ------------------------------------------------------------------ helpers

def _dialogue_progress(db: Session, user_id) -> dict:
    """dialogue_id -> {"status", "best_score", "in_progress_id"} across practice and mock attempts."""
    out: dict = {}
    rows = db.scalars(select(DialogueAttempt).where(DialogueAttempt.user_id == user_id)).all()
    for da in rows:
        p = out.setdefault(da.dialogue_id, {"status": "not_started", "best_score": None, "in_progress_id": None,
                                             "attempts": 0})
        p["attempts"] += 1
        if da.status == AttemptStatus.IN_PROGRESS:
            p["status"] = "in_progress"
            if da.mock_test_attempt_id is None:
                p["in_progress_id"] = str(da.id)
        elif da.status == AttemptStatus.COMPLETED and p["status"] != "in_progress":
            p["status"] = "completed"
        if da.total_score is not None and (p["best_score"] is None or da.total_score > p["best_score"]):
            p["best_score"] = da.total_score
    return out


def attempt_summary(db: Session, ref: svc.AttemptRef) -> dict:
    das = ref.dialogue_attempts
    scored = ref.mock.total_score if ref.mock else das[0].total_score
    max_score = ref.mock.maximum_score if ref.mock else das[0].maximum_score
    result = (ref.mock.result if ref.mock else das[0].result)
    scoring = ref.mock.scoring_status if ref.mock else das[0].scoring_status
    started = ref.mock.started_at if ref.mock else das[0].started_at
    answered = sum(1 for da in das for sa in da.segment_attempts if sa.audio_user)
    total = sum(len(da.segment_attempts) for da in das)
    return {"id": str(ref.id), "kind": ref.kind, "title": ref.mock.mock_test.title if ref.mock else das[0].dialogue.title,
            "dialogues": [da.dialogue.title for da in das], "status": ref.status.value,
            "scoring_status": scoring.value, "total_score": scored, "maximum_score": max_score,
            "result": result.value if result else None, "answered": answered, "segments": total,
            "started_at": started.isoformat() if started else None}


def _my_attempts(db: Session, user_id) -> list[svc.AttemptRef]:
    refs = [svc.AttemptRef("mock", m, list(m.dialogue_attempts)) for m in db.scalars(
        select(MockTestAttempt).where(MockTestAttempt.user_id == user_id))]
    refs += [svc.AttemptRef("practice", None, [d]) for d in db.scalars(
        select(DialogueAttempt).where(DialogueAttempt.user_id == user_id, DialogueAttempt.mock_test_attempt_id.is_(None)))]
    return sorted(refs, key=lambda r: (r.mock or r.dialogue_attempts[0]).started_at or utcnow(), reverse=True)


# ------------------------------------------------------------------ library

@router.get("/topics")
def topics(db: Session = Depends(get_db)):
    rows = db.scalars(select(Topic).where(Topic.status == RecordStatus.ACTIVE).order_by(Topic.sort_order, Topic.name))
    return [{"id": str(t.id), "name": t.name} for t in rows]


@router.get("/dialogues")
def dialogues(topic: str = "", difficulty: str = "", cu: CurrentUser = Depends(current_user),
              db: Session = Depends(get_db)):
    query = select(Dialogue).where(Dialogue.status == ContentStatus.PUBLISHED).order_by(Dialogue.sort_order, Dialogue.title)
    if topic:
        query = query.join(Topic).where(Topic.name == topic)
    if difficulty:
        query = query.where(Dialogue.difficulty == difficulty)
    progress = _dialogue_progress(db, cu.id)
    out = []
    for d in db.scalars(query):
        p = progress.get(d.id, {"status": "not_started", "best_score": None, "in_progress_id": None, "attempts": 0})
        out.append({"id": str(d.id), "title": d.title, "description": d.description,
                    "topic": d.topic.name if d.topic else None, "difficulty": d.difficulty.value,
                    "segments": sum(1 for s in d.segments if s.active), "estimated_duration": d.estimated_duration,
                    "maximum_score": d.maximum_score, "is_free": d.is_free, "locked": is_locked(cu.user, d.is_free), **p})
    return out


@router.get("/mock-tests")
def mock_tests(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for m in db.scalars(select(MockTest).where(MockTest.status == ContentStatus.PUBLISHED).order_by(MockTest.sort_order)):
        attempts = db.scalars(select(MockTestAttempt).where(MockTestAttempt.user_id == cu.id,
                                                            MockTestAttempt.mock_test_id == m.id)
                              .order_by(MockTestAttempt.started_at.desc())).all()
        in_progress = next((a for a in attempts if a.status == AttemptStatus.IN_PROGRESS), None)
        best = max((a.total_score for a in attempts if a.total_score is not None), default=None)
        out.append({"id": str(m.id), "title": m.title, "is_free": m.is_free, "locked": is_locked(cu.user, m.is_free),
                    "dialogues": [{"title": md.dialogue.title, "topic": md.dialogue.topic.name if md.dialogue.topic else None,
                                   "difficulty": md.dialogue.difficulty.value} for md in m.dialogues],
                    "attempts": len(attempts), "best_score": best,
                    "in_progress_id": str(in_progress.id) if in_progress else None})
    return out


# ------------------------------------------------------------------ dashboard

@router.get("/dashboard")
def dashboard(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    refs = _my_attempts(db, cu.id)
    summaries = [attempt_summary(db, r) for r in refs]
    mock_scores = [s["total_score"] for s in summaries if s["kind"] == "mock" and s["total_score"] is not None]
    dialogue_scores = [da.total_score for r in refs for da in r.dialogue_attempts if da.total_score is not None]
    unfinished = [s for s in summaries if s["status"] == AttemptStatus.IN_PROGRESS.value]
    library = dialogues("", "", cu, db)
    available = [d for d in library if not d["locked"]]
    quick = next((d for d in available if d["status"] == "not_started"), available[0] if available else None)
    exam = cu.user.target_exam_date
    return {
        "user": {"first_name": cu.user.first_name, "has_active_plan": has_active_plan(cu.user),
                 "target_exam_date": exam.isoformat() if exam else None,
                 "days_to_exam": (exam - date.today()).days if exam else None},
        "average_mock_score": round(sum(mock_scores) / len(mock_scores), 1) if mock_scores else None,
        "average_dialogue_score": round(sum(dialogue_scores) / len(dialogue_scores), 1) if dialogue_scores else None,
        "mock_max": scoring_config()["total_max"], "dialogue_max": scoring_config()["dialogue_max"],
        "dialogues_available": len(available), "dialogues_total": len(library),
        "mock_tests_available": sum(1 for m in mock_tests(cu, db) if not m["locked"]),
        "unfinished": unfinished[:3],
        "recent": [s for s in summaries if s["status"] != AttemptStatus.IN_PROGRESS.value][:6],
        "quick_start": quick,
        "upcoming_webinars": [],  # later phase
    }


@router.get("/attempts")
def my_attempts(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return [attempt_summary(db, r) for r in _my_attempts(db, cu.id)]


# ------------------------------------------------------------------ player

class StartIn(BaseModel):
    dialogue_id: uuid.UUID | None = None
    mock_test_id: uuid.UUID | None = None


@router.post("/attempts")
def start(body: StartIn, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    if bool(body.dialogue_id) == bool(body.mock_test_id):
        raise HTTPException(400, "Give either dialogue_id or mock_test_id")
    if body.dialogue_id:
        d = db.get(Dialogue, body.dialogue_id)
        if not d or d.status != ContentStatus.PUBLISHED:
            raise HTTPException(404, "Dialogue not found")
        ensure_access(cu.user, d.is_free)
        ref = svc.start_practice(db, cu.user, d)
    else:
        m = db.get(MockTest, body.mock_test_id)
        if not m or m.status != ContentStatus.PUBLISHED:
            raise HTTPException(404, "Mock test not found")
        ensure_access(cu.user, m.is_free)
        ref = svc.start_mock(db, cu.user, m)
    return {"id": str(ref.id), "kind": ref.kind}


@router.get("/attempts/{attempt_id}/state")
def attempt_state(attempt_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return svc.state(svc.resolve(db, attempt_id, cu.user))


class StepIn(BaseModel):
    step: str


@router.post("/attempts/{attempt_id}/step")
def save_step(attempt_id: uuid.UUID, body: StepIn, cu: CurrentUser = Depends(current_user),
              db: Session = Depends(get_db)):
    ref = svc.resolve(db, attempt_id, cu.user)
    svc.require_in_progress(ref)
    if body.step not in svc.STEPS:
        raise HTTPException(400, "Unknown step")
    ref.set_step(body.step)
    db.commit()
    return {"ok": True}


@router.post("/attempts/{attempt_id}/segments/{segment_attempt_id}/play")
def play(attempt_id: uuid.UUID, segment_attempt_id: uuid.UUID, cu: CurrentUser = Depends(current_user),
         db: Session = Depends(get_db)):
    ref = svc.resolve(db, attempt_id, cu.user)
    sa = svc.segment_attempt(ref, segment_attempt_id)
    is_repeat = svc.register_play(db, ref, sa)
    grant, exp = protection.new_grant(db, sa.id, cu.id, cu.sid)
    db.commit()
    return {"url": protection.signed_url(str(grant.id), "index.m3u8", exp), "is_repeat": is_repeat,
            "play_count": sa.play_count, "max_plays": ccl_config()["segment"]["max_plays"],
            "expires_in": get_settings().signed_url_ttl_seconds}


@router.get("/attempts/{attempt_id}/segments/{segment_attempt_id}/waveform")
def waveform(attempt_id: uuid.UUID, segment_attempt_id: uuid.UUID, cu: CurrentUser = Depends(current_user),
             db: Session = Depends(get_db)):
    sa = svc.segment_attempt(svc.resolve(db, attempt_id, cu.user, allow_admin=True), segment_attempt_id)
    data = get_storage().get(sa.segment.waveform_image) if sa.segment.waveform_image else None
    if not data:
        raise HTTPException(404, "No waveform")
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@router.put("/attempts/{attempt_id}/segments/{segment_attempt_id}/recording/parts/{index}")
async def upload_part(attempt_id: uuid.UUID, segment_attempt_id: uuid.UUID, index: int, request: Request,
                      cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    ratelimit.enforce(f"upload:{cu.id}", 240)
    ref = svc.resolve(db, attempt_id, cu.user)
    sa = svc.segment_attempt(ref, segment_attempt_id)
    max_bytes = ccl_config()["recording"]["max_upload_mb"] * 1024 * 1024
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > max_bytes:
            raise HTTPException(413, "Recording part too large")
    svc.save_part(ref, sa, index, bytes(body))
    return {"ok": True, "index": index, "bytes": len(body)}


class CompleteIn(BaseModel):
    parts: int
    mime: str = "audio/webm"
    duration_seconds: float | None = None
    timing: dict = {}


@router.post("/attempts/{attempt_id}/segments/{segment_attempt_id}/recording/complete")
def complete(attempt_id: uuid.UUID, segment_attempt_id: uuid.UUID, body: CompleteIn,
             cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    ref = svc.resolve(db, attempt_id, cu.user)
    sa = svc.segment_attempt(ref, segment_attempt_id)
    if body.parts < 1 or body.parts > 10000:
        raise HTTPException(400, "parts must be at least 1")
    svc.complete_recording(db, ref, sa, body.parts, body.mime, body.timing, body.duration_seconds)
    db.commit()
    return {"ok": True, "record_count": sa.record_count}


@router.post("/attempts/{attempt_id}/segments/{segment_attempt_id}/recording")
async def upload_recording(attempt_id: uuid.UUID, segment_attempt_id: uuid.UUID, audio: UploadFile = File(...),
                           timing: str = Form("{}"), duration_seconds: float | None = Form(None),
                           cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """Single-request upload (small recordings, or a fallback when chunked upload is not possible)."""
    ref = svc.resolve(db, attempt_id, cu.user)
    sa = svc.segment_attempt(ref, segment_attempt_id)
    max_bytes = ccl_config()["recording"]["max_upload_mb"] * 1024 * 1024
    data = await audio.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, "Recording too large")
    svc.save_part(ref, sa, 0, data)
    try:
        timing_dict = json.loads(timing or "{}")
    except json.JSONDecodeError:
        timing_dict = {}
    svc.complete_recording(db, ref, sa, 1, audio.content_type or "audio/webm", timing_dict, duration_seconds)
    db.commit()
    return {"ok": True, "record_count": sa.record_count}


@router.get("/attempts/{attempt_id}/segments/{segment_attempt_id}/recording")
def recording(attempt_id: uuid.UUID, segment_attempt_id: uuid.UUID, cu: CurrentUser = Depends(current_user),
              db: Session = Depends(get_db)):
    """Protected playback of the student's own answer (student who owns it, or an admin)."""
    sa = svc.segment_attempt(svc.resolve(db, attempt_id, cu.user, allow_admin=True), segment_attempt_id)
    data = get_storage().get(sa.audio_user) if sa.audio_user else None
    if not data:
        raise HTTPException(404, "No recording")
    return Response(data, media_type=sa.audio_mime or "audio/webm",
                    headers={"Cache-Control": "private, no-store", "Content-Disposition": "inline"})


class IntegrityIn(BaseModel):
    type: str
    detail: str = ""


@router.post("/attempts/{attempt_id}/integrity")
def integrity(attempt_id: uuid.UUID, body: IntegrityIn, cu: CurrentUser = Depends(current_user),
              db: Session = Depends(get_db)):
    ref = svc.resolve(db, attempt_id, cu.user)
    if body.type not in ("tab_blur", "reload", "mic_denied", "audio_error"):
        raise HTTPException(400, "Unknown event")
    da = ref.dialogue_attempts[0]
    da.integrity_events = [*(da.integrity_events or []),
                           {"type": body.type, "detail": body.detail[:200], "at": utcnow().isoformat()}][-200:]
    db.commit()
    return {"ok": True}


@router.post("/attempts/{attempt_id}/submit")
def submit(attempt_id: uuid.UUID, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    ref = svc.resolve(db, attempt_id, cu.user)
    svc.submit(db, ref)
    db.commit()
    return {"ok": True, "scoring_status": ScoringStatus.PENDING.value}
