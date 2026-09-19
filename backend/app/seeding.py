"""Demo data: dialogues, accounts, and Priya's history.

generate_media=True  (local `python seed.py`): voices any changed segments with TTS and
                     writes encrypted HLS into data/media, plus sample answers into data/seed_audio.
generate_media=False (deployed app, first boot): uses only the bundled audio. No TTS, no writes.
"""
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import hash_password
from .db import Base, SessionLocal, engine
from .models import Activity, Attempt, IssueReport, MockTest, Segment, SegmentResponse, User, utcnow
from .services.marking import MarkingError, mark_response
from .settings import BASE_DIR, get_settings

log = logging.getLogger("seeding")
CONTENT = BASE_DIR / "content" / "dialogues"
PASSWORD = "demo1234"
USERS = [
    ("priya@example.com", "Priya Sharma", "student", 38, "hi"),
    ("arjun@example.com", "Arjun Mehta", "student", None, None),
    ("assessor@example.com", "Meera Iyer (Assessor)", "assessor", None, None),
]


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _playlist_duration(playlist: str) -> float:
    return round(sum(float(l.split(":")[1].rstrip(",")) for l in playlist.splitlines() if l.startswith("#EXTINF")), 2)


def _segment_media(job, generate: bool, fresh: bool):
    from .services.media_pipeline import build_segment_media
    activity_id, order, txt, voice = job
    out_dir = get_settings().media_dir / f"{activity_id}/{order:02d}"
    stamp, playlist = out_dir / ".source", out_dir / "index.m3u8"
    h = _hash(txt, voice)
    if not fresh and stamp.exists() and stamp.read_text() == h and playlist.exists():
        return job, f"{activity_id}/{order:02d}", _playlist_duration(playlist.read_text())
    if not generate:
        raise RuntimeError(f"Bundled audio missing or stale for {activity_id}/{order:02d}. Run `python seed.py` locally.")
    key, dur = build_segment_media(activity_id, order, txt, voice, to_storage=False)
    stamp.write_text(h)
    return job, key, dur


def _student_audio(job, generate: bool, fresh: bool) -> str:
    """Returns the storage key of a synthetic 'student' recording."""
    from .services.media_pipeline import synthesize_student_answer
    txt, lang = job
    rel = f"seed_audio/{_hash(txt, lang)}.mp3"
    path = get_settings().data_dir / rel
    if fresh or not path.exists():
        if not generate:
            raise RuntimeError(f"Bundled sample answer missing: {rel}. Run `python seed.py` locally.")
        synthesize_student_answer(txt, lang, path)
    return rel


def seed_database(db: Session, generate_media: bool = False, fresh: bool = False) -> None:
    from .services.media_pipeline import voice_for

    # ---------------------------------------------------------- dialogues
    jobs, acts = [], []
    for n, f in enumerate(sorted(CONTENT.glob("*.yaml")), start=1):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        act = Activity(id=d["id"], number=n, title=d["title"], scenario=d["scenario"], domain=d["domain"],
                       difficulty=d["difficulty"], language_pair=d.get("language_pair", "hi-en"),
                       config_json={"speakers": d["speakers"]}, status="published")
        db.add(act)
        for i, s in enumerate(d["segments"], start=1):
            db.add(Segment(activity_id=act.id, order=i, speaker=s["speaker"], source_text=s["text"],
                           reference_text=s["reference"], sample_student_text=s.get("student", "")))
            jobs.append((act.id, i, s["text"], voice_for(s["speaker"], d["speakers"][s["speaker"]]["gender"])))
        acts.append(act)
    db.commit()

    with ThreadPoolExecutor(max_workers=6 if generate_media else 1) as pool:
        for (activity_id, order, _, _), key, dur in pool.map(lambda j: _segment_media(j, generate_media, fresh), jobs):
            seg = db.query(Segment).filter_by(activity_id=activity_id, order=order).one()
            seg.asset_key, seg.duration_seconds = key, dur
    db.commit()

    # ---------------------------------------------------------- users + mocks
    users = {}
    for email, name, role, exam_in_days, lang in USERS:
        u = User(email=email, name=name, role=role, password_hash=hash_password(PASSWORD),
                 exam_date=date.today() + timedelta(days=exam_in_days) if exam_in_days else None,
                 test_language=lang)
        db.add(u)
        users[email] = u
    by_domain = {a.domain: a for a in acts}
    db.add_all([
        MockTest(id="mock-1", title="Mock Test 1", activity_ids=[by_domain["Health"].id, by_domain["Legal"].id]),
        MockTest(id="mock-2", title="Mock Test 2", activity_ids=[by_domain["Consumer Affairs"].id, by_domain["Community"].id]),
    ])
    db.commit()

    # ---------------------------------------------------------- Priya's history
    priya = users["priya@example.com"]
    plans = [
        ("practice", [by_domain["Financial"]], 6, {}),
        ("practice", [by_domain["Education"]], 4, {2: 2}),
        ("mock", [by_domain["Health"], by_domain["Legal"]], 2, {3: 2, 12: 2, 17: 2}),
    ]
    seeded = []
    for mode, activities, days_ago, plays_override in plans:
        plan = [{"activity_id": a.id, "segment_id": s.id} for a in activities for s in a.segments]
        started = utcnow() - timedelta(days=days_ago, hours=2)
        blur = [{"type": "tab_blur", "index": 9, "detail": "", "at": (started + timedelta(minutes=9)).isoformat() + "Z"},
                {"type": "tab_focus", "index": 9, "detail": "", "at": (started + timedelta(minutes=9, seconds=14)).isoformat() + "Z"}]
        att = Attempt(user_id=priya.id, mode=mode, plan_json=plan, current_index=len(plan),
                      activity_id=activities[0].id if mode == "practice" else None,
                      mock_test_id="mock-1" if mode == "mock" else None,
                      plays_json={str(i): plays_override.get(i, 1) for i in range(len(plan))},
                      status="marked", started_at=started, submitted_at=started + timedelta(minutes=24),
                      integrity_events_json=blur if mode == "mock" else [])
        db.add(att)
        db.flush()
        seeded.append((att, [s for a in activities for s in a.segments]))
    db.commit()

    audio_jobs = sorted({(s.sample_student_text, s.target_language) for _, segs in seeded for s in segs})
    with ThreadPoolExecutor(max_workers=6 if generate_media else 1) as pool:
        keys = dict(zip(audio_jobs, pool.map(lambda j: _student_audio(j, generate_media, fresh), audio_jobs)))

    responses = []
    for att, segs in seeded:
        for idx, seg in enumerate(segs):
            r = SegmentResponse(attempt_id=att.id, seg_index=idx, segment_id=seg.id,
                                audio_key=keys[(seg.sample_student_text, seg.target_language)],
                                audio_mime="audio/mpeg", transcript=seg.sample_student_text,
                                stt_provider="seed", stt_confidence=0.93, status="uploaded",
                                created_at=att.started_at + timedelta(minutes=idx))
            db.add(r)
            responses.append(r)
    db.commit()

    marker = get_settings().resolved_marker

    def _mark(rid):
        s = SessionLocal()
        try:
            r = s.get(SegmentResponse, rid)
            try:
                mark_response(s, r)
                r.status = "marked"
            except MarkingError as e:
                r.status, r.error = "error", str(e)
            s.commit()
            return r.status
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=4 if marker == "claude" else 1) as pool:
        results = list(pool.map(_mark, [r.id for r in responses]))
    log.info("seeded: marked %s, errors %s (marker=%s)", results.count("marked"), results.count("error"), marker)

    db.add(IssueReport(user_id=priya.id, activity_id=by_domain["Legal"].id,
                       text="Segment 5: the Hindi speaker talks quite fast. Is this the real exam speed?"))
    db.commit()


def ensure_seeded() -> None:
    """Create tables and seed once. Safe when several serverless instances start together."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        is_pg = engine.dialect.name == "postgresql"
        if is_pg:
            db.execute(text("SELECT pg_advisory_lock(73101)"))
        try:
            if db.query(User).count() == 0:
                log.info("empty database: seeding demo data")
                seed_database(db, generate_media=False)
        finally:
            if is_pg:
                db.execute(text("SELECT pg_advisory_unlock(73101)"))
                db.commit()
    finally:
        db.close()
