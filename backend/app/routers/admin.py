import re
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import CurrentUser, assessor_user
from ..db import SessionLocal, get_db
from ..models import (Activity, Attempt, IssueReport, Marking, PlayGrant, SecurityEvent, Segment,
                      SegmentResponse, User, utcnow)
from ..services import storage
from ..services.marking import points_for
from ..services.media_pipeline import build_segment_media, voice_for
from ..services.scoring import attempt_results, dialogue_groups
from ..settings import get_settings, rubric_config

router = APIRouter(prefix="/api/admin")


@router.get("/attempts")
def list_attempts(cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    out = []
    for a in db.query(Attempt).order_by(Attempt.started_at.desc()).all():
        titles = [db.get(Activity, aid).title for aid in dialogue_groups(a)]
        row = {"id": a.id, "student": a.user.name, "student_email": a.user.email, "flagged": a.user.flagged,
               "mode": a.mode, "titles": titles, "status": a.status,
               "started_at": a.started_at.isoformat() + "Z",
               "tab_blurs": sum(1 for e in a.integrity_events_json or [] if e.get("type") == "tab_blur"),
               "needs_review": sum(1 for r in a.responses if r.needs_review),
               "total": None, "total_max": None, "passed": None, "reviewed": False}
        if a.status != "in_progress":
            r = attempt_results(db, a)
            row.update(total=r["total"], total_max=r["total_max"], passed=r["passed"],
                       reviewed=r["reviewed_by_assessor"])
        out.append(row)
    return out


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: str, cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    a = db.get(Attempt, attempt_id)
    if not a:
        raise HTTPException(404, "Not found")
    data = attempt_results(db, a, include_raw=True) if a.status != "in_progress" else {"status": a.status}
    data["student"] = {"name": a.user.name, "email": a.user.email, "flagged": a.user.flagged}
    data["integrity_events"] = a.integrity_events_json or []
    data["rubric"] = rubric_config()
    return data


class OverrideIn(BaseModel):
    issues: list[dict]
    note: str


@router.post("/responses/{response_id}/override")
def override(response_id: str, body: OverrideIn, cu: CurrentUser = Depends(assessor_user),
             db: Session = Depends(get_db)):
    resp = db.get(SegmentResponse, response_id)
    if not resp:
        raise HTTPException(404, "Not found")
    if not body.note.strip():
        raise HTTPException(400, "A note is required when overriding")
    valid = {(c["id"], ch["id"]) for c in rubric_config()["categories"] for ch in c["checks"]}
    sev = rubric_config()["severity_points"]
    clean = []
    for i in body.issues:
        if (i.get("category"), i.get("check")) not in valid or i.get("severity") not in sev:
            raise HTTPException(400, f"Invalid issue: {i}")
        clean.append({k: i.get(k, "") for k in ("category", "check", "severity", "quote", "explanation")})
    m = Marking(response_id=resp.id, source="assessor", marker=cu.user.name, issues_json=clean,
                points_deducted=points_for(clean), note=body.note.strip(), created_by=cu.id,
                summary="Reviewed by assessor.")
    db.add(m)
    resp.needs_review = False
    db.commit()
    return attempt_results(db, resp.attempt, include_raw=True)


@router.get("/reports")
def reports(cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    return [{"id": r.id, "student": r.user.name, "activity": r.activity.title, "text": r.text,
             "status": r.status, "created_at": r.created_at.isoformat() + "Z"}
            for r in db.query(IssueReport).order_by(IssueReport.created_at.desc()).all()]


@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: str, cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    r = db.get(IssueReport, report_id)
    if not r:
        raise HTTPException(404, "Not found")
    r.status = "resolved"
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ content ops

class NewDialogueIn(BaseModel):
    title: str
    scenario: str
    domain: str
    difficulty: str
    en_role: str = "Professional"
    en_gender: str = "female"
    hi_role: str = "Client"
    hi_gender: str = "male"
    script: str


def parse_script(script: str) -> list[dict]:
    """Format:
        EN: English segment
        REF: Hindi reference interpretation
        HI: Hindi segment
        REF: English reference interpretation
    """
    segments, current = [], None
    for raw in script.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(EN|HI|REF)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if not m:
            raise HTTPException(400, f'Could not read line: "{line[:60]}". Start each line with EN:, HI: or REF:')
        tag, text = m.group(1).upper(), m.group(2).strip()
        if tag in ("EN", "HI"):
            current = {"speaker": tag.lower(), "text": text, "reference": ""}
            segments.append(current)
        else:
            if not current or current["reference"]:
                raise HTTPException(400, "Each REF: line must follow one EN: or HI: line")
            current["reference"] = text
    if len(segments) < 2:
        raise HTTPException(400, "A dialogue needs at least two segments")
    missing = [i + 1 for i, s in enumerate(segments) if not s["reference"]]
    if missing:
        raise HTTPException(400, f"Segments missing a REF: line: {missing}")
    long = [i + 1 for i, s in enumerate(segments) if len(s["text"].split()) > 45]
    if long:
        raise HTTPException(400, f"Segments too long for CCL (keep under ~35 words): {long}")
    return segments


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "dialogue"


@router.post("/activities")
def create_activity(body: NewDialogueIn, background: BackgroundTasks, cu: CurrentUser = Depends(assessor_user),
                    db: Session = Depends(get_db)):
    segs = parse_script(body.script)
    base = _slug(f"{body.domain}-{body.title}")
    aid, n = base, 2
    while db.get(Activity, aid):
        aid, n = f"{base}-{n}", n + 1
    number = (max([a.number for a in db.query(Activity).all()] or [0])) + 1
    act = Activity(id=aid, number=number, title=body.title.strip(), scenario=body.scenario.strip(),
                   domain=body.domain, difficulty=body.difficulty, status="processing",
                   config_json={"speakers": {"en": {"role": body.en_role, "gender": body.en_gender},
                                             "hi": {"role": body.hi_role, "gender": body.hi_gender}}})
    db.add(act)
    for i, s in enumerate(segs, start=1):
        db.add(Segment(activity_id=aid, order=i, speaker=s["speaker"], source_text=s["text"],
                       reference_text=s["reference"]))
    db.commit()
    background.add_task(generate_activity_media, aid)
    return {"id": aid, "status": "processing", "segments": len(segs)}


def generate_activity_media(activity_id: str) -> None:
    db = SessionLocal()
    try:
        act = db.get(Activity, activity_id)
        speakers = (act.config_json or {}).get("speakers", {})
        try:
            for seg in act.segments:
                gender = speakers.get(seg.speaker, {}).get("gender", "female")
                key, dur = build_segment_media(act.id, seg.order, seg.source_text, voice_for(seg.speaker, gender))
                seg.asset_key, seg.duration_seconds = key, dur
                act.status_detail = f"Generated {seg.order}/{len(act.segments)} segments"
                db.commit()
            act.status, act.status_detail = "published", ""
        except Exception as e:
            act.status, act.status_detail = "failed", f"{type(e).__name__}: {e}"
        db.commit()
    finally:
        db.close()


@router.get("/activities")
def admin_activities(cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    return [{"id": a.id, "number": a.number, "title": a.title, "domain": a.domain, "difficulty": a.difficulty,
             "status": a.status, "status_detail": a.status_detail, "segment_count": len(a.segments),
             "created_at": a.created_at.isoformat() + "Z"}
            for a in db.query(Activity).order_by(Activity.number.desc()).all()]


# ------------------------------------------------------------------ protection panel

@router.get("/protection")
def protection_status(cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    s = get_settings()
    since = utcnow() - timedelta(hours=24)
    events = db.query(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(30).all()
    kinds = Counter(e.kind for e in db.query(SecurityEvent).filter(SecurityEvent.created_at >= since))

    # Inspect what is actually on disk for one dialogue, so the claim is verifiable.
    sample = db.query(Activity).filter(Activity.status == "published").order_by(Activity.number).first()
    sample_info = None
    if sample and sample.segments:
        base = f"media/{sample.segments[0].asset_key}"
        files = [k.rsplit("/", 1)[1] for k in storage.list_keys(base, db)]
        playlist = (storage.read(f"{base}/index.m3u8", db) or b"").decode("utf-8")
        media_root = s.media_dir
        plain_audio = [p.name for p in media_root.rglob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a")
                       and p.name != "chime.wav"]
        plain_audio += [k for k in storage.list_keys("media", db)
                        if k.endswith((".mp3", ".wav", ".m4a")) and not k.endswith("chime.wav")]
        sample_info = {
            "dialogue": sample.title,
            "files": files,
            "encrypted": "METHOD=AES-128" in playlist,
            "segment_count": playlist.count("#EXTINF"),
            "plain_audio_files_on_server": len(plain_audio),
        }
    users = {u.id: u.name for u in db.query(User).all()}
    return {
        "controls": [
            {"name": "Segmented streaming (HLS)", "status": "on", "detail": "Each segment split into ~4s chunks. There is no single file to download."},
            {"name": "AES-128 encryption", "status": "on", "detail": "Chunks are encrypted. The key is only served to the logged-in owner of the attempt."},
            {"name": "Signed, expiring URLs", "status": "on", "detail": f"Every URL expires after {s.signed_url_ttl_seconds // 60} minutes."},
            {"name": "Session-bound playback", "status": "on", "detail": "URLs are tied to the attempt and login session. A copied link fails elsewhere."},
            {"name": "Server-enforced play count", "status": "on", "detail": "Refresh, back button or a second tab cannot get another play."},
            {"name": "No bulk content endpoint", "status": "on", "detail": "Dialogue text and references never reach the browser during a test."},
            {"name": "Rate limiting + anomaly flag", "status": "on", "detail": f"More than {s.media_requests_per_minute} media requests/min flags the account."},
            {"name": "Per-user audio watermarking", "status": "planned", "detail": "Not in the demo. Makes a soundcard recording traceable to the account it came from."},
        ],
        "sample": sample_info,
        "grants_24h": db.query(PlayGrant).filter(PlayGrant.created_at >= since).count(),
        "events_24h": dict(kinds),
        "flagged_users": [{"name": u.name, "email": u.email} for u in db.query(User).filter(User.flagged).all()],
        "recent_events": [{"kind": e.kind, "detail": e.detail, "user": users.get(e.user_id, "anonymous"),
                           "ip": e.ip, "at": e.created_at.isoformat() + "Z"} for e in events],
    }


@router.post("/protection/unflag")
def unflag_all(cu: CurrentUser = Depends(assessor_user), db: Session = Depends(get_db)):
    for u in db.query(User).filter(User.flagged).all():
        u.flagged = False
    db.commit()
    return {"ok": True}
