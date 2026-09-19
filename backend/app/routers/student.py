from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import CurrentUser, current_user
from ..db import get_db
from ..models import Activity, Attempt, IssueReport, MockTest, SegmentResponse, utcnow
from ..services import protection
from ..services.processing import process_response
from ..services.scoring import attempt_results, dialogue_groups, repeats_used
from ..settings import ccl_config, get_settings

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ library

def activity_dict(a: Activity) -> dict:
    return {
        "id": a.id, "number": a.number, "title": a.title, "scenario": a.scenario,
        "domain": a.domain, "difficulty": a.difficulty, "language_pair": a.language_pair,
        "segment_count": len(a.segments), "status": a.status,
        "duration_seconds": round(sum(s.duration_seconds for s in a.segments)),
        "speakers": (a.config_json or {}).get("speakers", {}),
    }


@router.get("/activities")
def list_activities(domain: str | None = None, difficulty: str | None = None, q: str | None = None,
                    cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Activity).filter(Activity.status == "published")
    if cu.user.role == "student":
        query = query.filter(Activity.language_pair == f"{cu.user.test_language or 'hi'}-en")
    if domain:
        query = query.filter(Activity.domain == domain)
    if difficulty:
        query = query.filter(Activity.difficulty == difficulty)
    items = [activity_dict(a) for a in query.order_by(Activity.number.desc()).all()]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["title"].lower() or ql in i["scenario"].lower()]
    practiced = {a.activity_id for a in db.query(Attempt).filter(Attempt.user_id == cu.id, Attempt.mode == "practice")}
    for i in items:
        i["practiced"] = i["id"] in practiced
    return items


@router.get("/mock-tests")
def list_mocks(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for m in db.query(MockTest).all():
        acts = [db.get(Activity, aid) for aid in m.activity_ids]
        last = (db.query(Attempt).filter(Attempt.user_id == cu.id, Attempt.mock_test_id == m.id)
                .order_by(Attempt.started_at.desc()).first())
        out.append({"id": m.id, "title": m.title,
                    "dialogues": [{"title": a.title, "domain": a.domain, "difficulty": a.difficulty} for a in acts],
                    "last_attempt": {"id": last.id, "status": last.status} if last else None})
    return out


class ReportIn(BaseModel):
    text: str


@router.post("/activities/{activity_id}/report")
def report_issue(activity_id: str, body: ReportIn, cu: CurrentUser = Depends(current_user),
                 db: Session = Depends(get_db)):
    if not db.get(Activity, activity_id):
        raise HTTPException(404, "Not found")
    db.add(IssueReport(user_id=cu.id, activity_id=activity_id, text=body.text.strip()[:2000]))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ dashboard

@router.get("/dashboard")
def dashboard(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    attempts = (db.query(Attempt).filter(Attempt.user_id == cu.id)
                .order_by(Attempt.started_at.desc()).all())
    finished = [a for a in attempts if a.status != "in_progress"]
    practiced = sum(len(dialogue_groups(a)) for a in finished)
    last_mock = next((a for a in finished if a.mode == "mock"), None)
    mock = None
    if last_mock:
        r = attempt_results(db, last_mock)
        mock = {"attempt_id": last_mock.id, "total": r["total"], "total_max": r["total_max"],
                "passed": r["passed"], "status": last_mock.status,
                "dialogues": [{"title": d["title"], "score": d["score"]} for d in r["dialogues"]]}
    recent = []
    for a in attempts[:6]:
        recent.append(_attempt_summary(db, a))
    latest = db.query(Activity).filter(Activity.status == "published").order_by(Activity.number.desc()).limit(6).all()
    days_left = (cu.user.exam_date - date.today()).days if cu.user.exam_date else None
    in_progress = next((a for a in attempts if a.status == "in_progress"), None)
    return {
        "user": {"name": cu.user.name, "exam_date": cu.user.exam_date.isoformat() if cu.user.exam_date else None,
                 "days_left": days_left},
        "total_practiced": practiced,
        "total_dialogues": db.query(Activity).filter(Activity.status == "published").count(),
        "mock": mock,
        "in_progress": _attempt_summary(db, in_progress) if in_progress else None,
        "recent_attempts": recent,
        "latest_dialogues": [activity_dict(a) for a in latest],
    }


def _attempt_summary(db: Session, a: Attempt) -> dict:
    titles = [db.get(Activity, aid).title for aid in dialogue_groups(a)]
    summary = {"id": a.id, "mode": a.mode, "status": a.status, "titles": titles,
               "started_at": a.started_at.isoformat() + "Z", "total": None, "total_max": None, "passed": None}
    if a.status in ("marked", "marking"):
        r = attempt_results(db, a)
        summary.update(total=r["total"], total_max=r["total_max"], passed=r["passed"])
    return summary


@router.get("/attempts")
def my_attempts(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    attempts = db.query(Attempt).filter(Attempt.user_id == cu.id).order_by(Attempt.started_at.desc()).all()
    return [_attempt_summary(db, a) for a in attempts]


# ------------------------------------------------------------------ attempts

class StartIn(BaseModel):
    mode: str  # practice | mock
    activity_id: str | None = None
    mock_test_id: str | None = None


@router.post("/attempts")
def start_attempt(body: StartIn, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    if body.mode == "practice":
        act = db.get(Activity, body.activity_id or "")
        if not act or act.status != "published":
            raise HTTPException(404, "Dialogue not found")
        activities = [act]
    elif body.mode == "mock":
        mock = db.get(MockTest, body.mock_test_id or "")
        if not mock:
            raise HTTPException(404, "Mock test not found")
        activities = [db.get(Activity, aid) for aid in mock.activity_ids]
    else:
        raise HTTPException(400, "mode must be practice or mock")

    # Resume instead of opening a second parallel attempt at the same thing.
    existing = (db.query(Attempt).filter(
        Attempt.user_id == cu.id, Attempt.status == "in_progress", Attempt.mode == body.mode,
        Attempt.activity_id == (body.activity_id if body.mode == "practice" else None),
        Attempt.mock_test_id == (body.mock_test_id if body.mode == "mock" else None)).first())
    if existing:
        return {"id": existing.id, "resumed": True}

    plan = [{"activity_id": a.id, "segment_id": s.id} for a in activities for s in a.segments]
    attempt = Attempt(user_id=cu.id, mode=body.mode, plan_json=plan,
                      activity_id=body.activity_id if body.mode == "practice" else None,
                      mock_test_id=body.mock_test_id if body.mode == "mock" else None)
    db.add(attempt)
    db.commit()
    return {"id": attempt.id, "resumed": False}


def _own_attempt(db: Session, attempt_id: str, cu: CurrentUser, allow_assessor: bool = False) -> Attempt:
    a = db.get(Attempt, attempt_id)
    if not a or (a.user_id != cu.id and not (allow_assessor and cu.user.role == "assessor")):
        raise HTTPException(404, "Attempt not found")
    return a


def _state(db: Session, a: Attempt) -> dict:
    cfg = ccl_config()
    groups = list(dialogue_groups(a).items())
    dialogues = []
    for aid, idxs in groups:
        act = db.get(Activity, aid)
        dialogues.append({"id": aid, "title": act.title, "domain": act.domain, "scenario": act.scenario,
                          "segment_count": len(idxs), "start_index": idxs[0],
                          "repeats_used": repeats_used(a, idxs)})
    current = None
    if a.status == "in_progress" and a.current_index < len(a.plan_json):
        item = a.plan_json[a.current_index]
        d_pos = next(i for i, (aid, idxs) in enumerate(groups) if a.current_index in idxs)
        act = db.get(Activity, item["activity_id"])
        seg = next(s for s in act.segments if s.id == item["segment_id"])
        plays = (a.plays_json or {}).get(str(a.current_index), 0)
        speakers = (act.config_json or {}).get("speakers", {})
        d_reps = dialogues[d_pos]["repeats_used"]
        current = {
            "index": a.current_index,
            "dialogue_position": d_pos,
            "segment_number": a.current_index - groups[d_pos][1][0] + 1,
            "speaker": seg.speaker,
            "speaker_role": speakers.get(seg.speaker, {}).get("role", ""),
            "target_language": seg.target_language,
            "plays": plays,
            "max_plays": 1 + cfg["repeats"]["max_per_segment"],
            "repeat_will_deduct": d_reps >= cfg["repeats"]["free_per_dialogue"],
        }
    return {
        "id": a.id, "mode": a.mode, "status": a.status, "total": len(a.plan_json),
        "index": a.current_index, "dialogues": dialogues, "current": current,
        "response_window_seconds": cfg["response_window_seconds"],
        "free_repeats_per_dialogue": cfg["repeats"]["free_per_dialogue"],
        "stt_provider": get_settings().resolved_stt,
        "language": next((l for l in cfg["languages"] if a.plan_json and
                          db.get(Activity, a.plan_json[0]["activity_id"]).language_pair.startswith(l["code"])), None),
        "stt_locales": {"en": cfg["english_stt_locale"],
                        **{l["code"]: l["stt_locale"] for l in cfg["languages"]}},
        "marker": get_settings().resolved_marker,
    }


@router.get("/attempts/{attempt_id}/state")
def attempt_state(attempt_id: str, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return _state(db, _own_attempt(db, attempt_id, cu))


@router.post("/attempts/{attempt_id}/play")
def play_segment(attempt_id: str, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """Server-enforced play count. Refresh, back button or a second tab cannot
    get another play: every play is recorded here before any audio URL exists."""
    a = _own_attempt(db, attempt_id, cu)
    if a.status != "in_progress" or a.current_index >= len(a.plan_json):
        raise HTTPException(409, "Attempt is not in progress")
    cfg = ccl_config()
    key = str(a.current_index)
    plays = dict(a.plays_json or {})
    if plays.get(key, 0) >= 1 + cfg["repeats"]["max_per_segment"]:
        raise HTTPException(409, "No plays left for this segment")
    plays[key] = plays.get(key, 0) + 1
    a.plays_json = plays
    is_repeat = plays[key] > 1
    if is_repeat:
        a.integrity_events_json = [*(a.integrity_events_json or []),
                                   {"type": "repeat", "index": a.current_index, "at": utcnow().isoformat() + "Z"}]
    seg_id = a.plan_json[a.current_index]["segment_id"]
    grant, exp = protection.new_grant(db, a.id, a.current_index, seg_id, cu.sid)
    db.commit()
    return {"url": protection.signed_url(grant.id, "index.m3u8", exp), "is_repeat": is_repeat,
            "plays": plays[key], "expires_in": get_settings().signed_url_ttl_seconds}


@router.post("/attempts/{attempt_id}/segments/{index}/audio")
async def upload_segment_audio(attempt_id: str, index: int, background: BackgroundTasks,
                               audio: UploadFile | None = File(default=None),
                               browser_stt: bool = Form(default=False),
                               browser_transcript: str | None = Form(default=None),
                               browser_confidence: float | None = Form(default=None),
                               cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    a = _own_attempt(db, attempt_id, cu)
    if a.status != "in_progress":
        raise HTTPException(409, "Attempt is not in progress")
    if index != a.current_index:
        raise HTTPException(409, f"Expected segment {a.current_index}")
    if (a.plays_json or {}).get(str(index), 0) < 1:
        raise HTTPException(409, "Segment has not been played")

    audio_key, mime = "", "audio/webm"
    if audio is not None:
        data = await audio.read()
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(413, "Recording too large")
        if len(data) > 1000:
            mime = (audio.content_type or "audio/webm").split(";")[0]
            ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3",
                   "audio/wav": "wav"}.get(mime, "webm")
            audio_key = f"{a.id}/{index:03d}.{ext}"
            path = get_settings().uploads_dir / audio_key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    resp = SegmentResponse(attempt_id=a.id, seg_index=index, segment_id=a.plan_json[index]["segment_id"],
                           audio_key=audio_key, audio_mime=mime)
    # Fallback STT: the browser's own speech recognition. Only used when the
    # server has no Whisper key; it is client-supplied, so never preferred.
    if get_settings().resolved_stt == "mock" and browser_stt and audio_key:
        resp.transcript = (browser_transcript or "").strip()[:2000]
        resp.stt_provider = "browser"
        resp.stt_confidence = browser_confidence
        # Recognition can fail silently (network, accent); don't auto-fail a spoken answer.
        resp.needs_review = not resp.transcript
    db.add(resp)
    a.current_index = index + 1
    done = a.current_index >= len(a.plan_json)
    if done:
        a.status, a.submitted_at = "marking", utcnow()
    db.commit()
    background.add_task(process_response, resp.id)
    return {"response_id": resp.id, "next_index": a.current_index, "done": done}


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, background: BackgroundTasks,
                   cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """End early: remaining segments are recorded as unanswered."""
    a = _own_attempt(db, attempt_id, cu)
    if a.status != "in_progress":
        return {"status": a.status}
    new_ids = []
    for idx in range(a.current_index, len(a.plan_json)):
        r = SegmentResponse(attempt_id=a.id, seg_index=idx, segment_id=a.plan_json[idx]["segment_id"])
        db.add(r)
        new_ids.append(r)
    a.current_index = len(a.plan_json)
    a.status, a.submitted_at = "marking", utcnow()
    db.commit()
    for r in new_ids:
        background.add_task(process_response, r.id)
    if not new_ids:
        from ..services.processing import finalize_if_done
        finalize_if_done(db, a.id)
    return {"status": "marking"}


class IntegrityIn(BaseModel):
    type: str
    detail: str = ""


@router.post("/attempts/{attempt_id}/integrity")
def integrity_event(attempt_id: str, body: IntegrityIn, cu: CurrentUser = Depends(current_user),
                    db: Session = Depends(get_db)):
    a = _own_attempt(db, attempt_id, cu)
    if body.type not in ("tab_blur", "tab_focus", "mic_denied", "reload"):
        raise HTTPException(400, "Unknown event")
    a.integrity_events_json = [*(a.integrity_events_json or []),
                               {"type": body.type, "index": a.current_index, "detail": body.detail[:200],
                                "at": utcnow().isoformat() + "Z"}]
    db.commit()
    return {"ok": True}


@router.get("/attempts/{attempt_id}/segments/{index}/feedback")
def segment_feedback(attempt_id: str, index: int, cu: CurrentUser = Depends(current_user),
                     db: Session = Depends(get_db)):
    """Practice mode only: instant per-segment feedback."""
    a = _own_attempt(db, attempt_id, cu)
    if a.mode != "practice":
        raise HTTPException(403, "Feedback is shown after the mock test")
    results = attempt_results(db, a)
    for d in results["dialogues"]:
        for s in d["segments"]:
            if s["index"] == index:
                return s
    raise HTTPException(404, "Not found")


@router.get("/attempts/{attempt_id}/results")
def results(attempt_id: str, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    a = _own_attempt(db, attempt_id, cu, allow_assessor=True)
    if a.status == "in_progress":
        raise HTTPException(409, "Attempt still in progress")
    return attempt_results(db, a)


@router.get("/attempts/{attempt_id}/responses/{response_id}/audio")
def response_audio(attempt_id: str, response_id: str, cu: CurrentUser = Depends(current_user),
                   db: Session = Depends(get_db)):
    a = _own_attempt(db, attempt_id, cu, allow_assessor=True)
    r = db.get(SegmentResponse, response_id)
    if not r or r.attempt_id != a.id or not r.audio_key:
        raise HTTPException(404, "No recording")
    path = Path(get_settings().uploads_dir / r.audio_key)
    return FileResponse(path, media_type=r.audio_mime, headers={"Cache-Control": "private, no-store"})
