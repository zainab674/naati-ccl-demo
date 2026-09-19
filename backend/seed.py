"""Reset the database and seed the demo.

    python seed.py            # reset DB, reuse generated audio where the text is unchanged
    python seed.py --fresh    # also regenerate all audio

Generated audio is cached by text hash, so re-seeding is fast.
"""
import hashlib
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import yaml

from app.db import Base, SessionLocal, engine
from app.models import Activity, Attempt, IssueReport, MockTest, Segment, SegmentResponse, User, utcnow
from app.auth import hash_password
from app.services.marking import MarkingError, mark_response
from app.services.media_pipeline import build_segment_media, synthesize_student_answer, voice_for
from app.settings import BASE_DIR, get_settings

settings = get_settings()
CONTENT = BASE_DIR / "content" / "dialogues"
FRESH = "--fresh" in sys.argv

USERS = [
    ("priya@example.com", "Priya Sharma", "student", date.today() + timedelta(days=38)),
    ("arjun@example.com", "Arjun Mehta", "student", None),
    ("assessor@example.com", "Meera Iyer (Assessor)", "assessor", None),
]
PASSWORD = "demo1234"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def build_media(job):
    activity_id, order, text, voice = job
    out_dir = settings.media_dir / f"{activity_id}/{order:02d}"
    stamp = out_dir / ".source"
    h = _hash(text, voice)
    if not FRESH and stamp.exists() and stamp.read_text() == h and (out_dir / "index.m3u8").exists():
        dur = sum(float(l.split(":")[1].rstrip(",")) for l in (out_dir / "index.m3u8").read_text().splitlines()
                  if l.startswith("#EXTINF"))
        return job, f"{activity_id}/{order:02d}", round(dur, 2)
    key, dur = build_segment_media(activity_id, order, text, voice)
    stamp.write_text(h)
    return job, key, dur


def student_audio(job):
    text, lang = job
    cache = settings.data_dir / "seed_audio" / f"{_hash(text, lang)}.mp3"
    if FRESH or not cache.exists():
        synthesize_student_answer(text, lang, cache)
    return job, cache


def main():
    print("Resetting database...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shutil.rmtree(settings.uploads_dir, ignore_errors=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(settings.media_dir / "zz-test", ignore_errors=True)
    db = SessionLocal()

    # ---------------------------------------------------------- dialogues
    files = sorted(CONTENT.glob("*.yaml"))
    jobs, acts = [], []
    for n, f in enumerate(files, start=1):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        act = Activity(id=d["id"], number=n, title=d["title"], scenario=d["scenario"], domain=d["domain"],
                       difficulty=d["difficulty"], language_pair=d.get("language_pair", "hi-en"),
                       config_json={"speakers": d["speakers"]}, status="published")
        db.add(act)
        for i, s in enumerate(d["segments"], start=1):
            seg = Segment(activity_id=act.id, order=i, speaker=s["speaker"], source_text=s["text"],
                          reference_text=s["reference"], sample_student_text=s.get("student", ""))
            db.add(seg)
            gender = d["speakers"][s["speaker"]]["gender"]
            jobs.append((act.id, i, s["text"], voice_for(s["speaker"], gender)))
        acts.append(act)
    db.commit()

    print(f"Generating encrypted HLS audio for {len(jobs)} segments...")
    with ThreadPoolExecutor(max_workers=6) as pool:
        for (activity_id, order, _, _), key, dur in pool.map(build_media, jobs):
            seg = db.query(Segment).filter_by(activity_id=activity_id, order=order).one()
            seg.asset_key, seg.duration_seconds = key, dur
    db.commit()

    # ---------------------------------------------------------- users + mock
    users = {}
    for email, name, role, exam in USERS:
        u = User(email=email, name=name, role=role, password_hash=hash_password(PASSWORD), exam_date=exam,
                 test_language="hi" if email == "priya@example.com" else None)
        db.add(u)
        users[email] = u
    by_domain = {a.domain: a for a in acts}
    mock = MockTest(id="mock-1", title="Mock Test 1", activity_ids=[by_domain["Health"].id, by_domain["Legal"].id])
    mock2 = MockTest(id="mock-2", title="Mock Test 2",
                     activity_ids=[by_domain["Consumer Affairs"].id, by_domain["Community"].id])
    db.add_all([mock, mock2])
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
        att = Attempt(user_id=priya.id, mode=mode, plan_json=plan, current_index=len(plan),
                      activity_id=activities[0].id if mode == "practice" else None,
                      mock_test_id="mock-1" if mode == "mock" else None,
                      plays_json={str(i): plays_override.get(i, 1) for i in range(len(plan))},
                      status="marked", started_at=started, submitted_at=started + timedelta(minutes=24),
                      integrity_events_json=([{"type": "tab_blur", "index": 9, "detail": "", "at": (started + timedelta(minutes=9)).isoformat() + "Z"},
                                              {"type": "tab_focus", "index": 9, "detail": "", "at": (started + timedelta(minutes=9, seconds=14)).isoformat() + "Z"}]
                                             if mode == "mock" else []))
        db.add(att)
        db.flush()
        segs = [s for a in activities for s in a.segments]
        seeded.append((att, segs))
    db.commit()

    audio_jobs = [(s.sample_student_text, s.target_language) for _, segs in seeded for s in segs]
    print(f"Synthesising {len(audio_jobs)} sample student answers...")
    with ThreadPoolExecutor(max_workers=6) as pool:
        audio = {job: path for job, path in pool.map(student_audio, audio_jobs)}

    marker = settings.resolved_marker
    print(f"Marking seeded answers with: {marker}")
    responses = []
    for att, segs in seeded:
        for idx, seg in enumerate(segs):
            key = f"{att.id}/{idx:03d}.mp3"
            dest = settings.uploads_dir / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(audio[(seg.sample_student_text, seg.target_language)], dest)
            r = SegmentResponse(attempt_id=att.id, seg_index=idx, segment_id=seg.id, audio_key=key,
                                audio_mime="audio/mpeg", transcript=seg.sample_student_text,
                                stt_provider="seed", stt_confidence=0.93, status="uploaded",
                                created_at=att.started_at + timedelta(minutes=idx))
            db.add(r)
            responses.append(r)
    db.commit()

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
    print(f"  marked {results.count('marked')}, errors {results.count('error')}")

    db.add(IssueReport(user_id=priya.id, activity_id=by_domain["Legal"].id,
                       text="Segment 5: the Hindi speaker talks quite fast. Is this the real exam speed?"))
    db.commit()

    from app.services.scoring import attempt_results
    for att, _ in seeded:
        r = attempt_results(db, db.get(Attempt, att.id))
        print(f"  {att.mode:8s} {r['total']}/{r['total_max']} "
              f"({', '.join(str(d['score']) for d in r['dialogues'])}) passed={r['passed']}")
    db.close()
    print("\nDone. Logins (password: demo1234):")
    for email, name, role, _ in USERS:
        print(f"  {role:9s} {email}")


if __name__ == "__main__":
    main()
