from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import (AttemptStatus, DialogueAttempt, Job, MockTestAttempt, RepeatEvent, SecurityEvent,
                        SegmentAttempt, SubscriptionStatus, User)

from .conftest import login, signup
from .factories import make_dialogue, make_mock


def activate(db, email="student@example.com"):
    u = db.scalar(select(User).where(User.email == email))
    u.subscription_status = SubscriptionStatus.ACTIVE
    db.commit()


def first_segment(state):
    return state["dialogues"][0]["segments"][0]["segment_attempt_id"]


def test_library_shows_locked_and_free(student_client, db):
    make_dialogue(db, key="free-one", is_free=True)
    make_dialogue(db, key="paid-one")
    rows = {d["title"]: d for d in student_client.get("/api/dialogues").json()}
    assert rows["Free One"]["locked"] is False and rows["Paid One"]["locked"] is True
    assert rows["Free One"]["status"] == "not_started"
    paid = rows["Paid One"]["id"]
    assert student_client.post("/api/attempts", json={"dialogue_id": paid}).status_code == 402
    assert student_client.post("/api/attempts", json={"dialogue_id": rows["Free One"]["id"]}).status_code == 200
    assert {d["title"] for d in student_client.get("/api/dialogues?topic=Legal").json()} == set()


def test_practice_flow_resume_and_no_answer_leak(student_client, db):
    d = make_dialogue(db, is_free=True, segments=2)
    r = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()
    assert r["kind"] == "practice"
    again = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()
    assert again["id"] == r["id"]  # resumes instead of starting a second attempt

    st = student_client.get(f"/api/attempts/{r['id']}/state").json()
    assert st["step"] == "info1" and len(st["dialogues"][0]["segments"]) == 2
    text = str(st)
    assert "Source transcript" not in text and "Meaning" not in text and "Reference" not in text

    student_client.post(f"/api/attempts/{r['id']}/step", json={"step": "segment"})
    assert student_client.get(f"/api/attempts/{r['id']}/state").json()["step"] == "segment"


def test_play_limits_repeats_and_protected_media(student_client, db):
    d = make_dialogue(db, is_free=True, segments=1)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    sid = first_segment(student_client.get(f"/api/attempts/{aid}/state").json())

    p1 = student_client.post(f"/api/attempts/{aid}/segments/{sid}/play").json()
    assert p1["is_repeat"] is False and p1["url"].startswith("/api/media/")
    playlist = student_client.get(p1["url"])
    assert playlist.status_code == 200 and "METHOD=AES-128" in playlist.text and "__KEY_URI__" not in playlist.text
    key_url = next(line.split('URI="')[1].split('"')[0] for line in playlist.text.splitlines() if "EXT-X-KEY" in line)
    seg_url = next(line for line in playlist.text.splitlines() if line.startswith("/api/media/") and ".ts" in line)
    assert student_client.get(key_url).content == b"0123456789abcdef"
    assert student_client.get(seg_url).status_code == 200

    # The same URL from another login session is refused, and logged.
    other = TestClient(app)
    login(other, "student@example.com", "student-pass-1")
    assert other.get(p1["url"]).status_code == 403
    assert db.scalar(select(SecurityEvent).where(SecurityEvent.kind == "session_mismatch")) is not None
    # Tampered signature
    assert student_client.get(p1["url"].replace("sig=", "sig=0")).status_code == 403

    p2 = student_client.post(f"/api/attempts/{aid}/segments/{sid}/play").json()
    assert p2["is_repeat"] is True and p2["play_count"] == 2
    assert student_client.post(f"/api/attempts/{aid}/segments/{sid}/play").status_code == 409
    assert db.query(RepeatEvent).count() == 1
    db.expire_all()
    assert db.scalar(select(DialogueAttempt)).total_repeats == 1


def test_chunked_recording_upload_and_playback(student_client, db):
    d = make_dialogue(db, is_free=True, segments=2)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    sid = first_segment(student_client.get(f"/api/attempts/{aid}/state").json())
    base = f"/api/attempts/{aid}/segments/{sid}/recording"
    # Cannot record before playing
    assert student_client.put(f"{base}/parts/0", content=b"x").status_code == 409
    student_client.post(f"/api/attempts/{aid}/segments/{sid}/play")
    assert student_client.put(f"{base}/parts/0", content=b"AAAA").status_code == 200
    assert student_client.put(f"{base}/parts/1", content=b"BBXX").status_code == 200
    assert student_client.put(f"{base}/parts/1", content=b"BBBB").status_code == 200  # retry overwrites
    # Missing part 2 -> clear error
    assert student_client.post(f"{base}/complete", json={"parts": 3, "mime": "audio/webm"}).status_code == 409
    r = student_client.post(f"{base}/complete", json={"parts": 2, "mime": "audio/webm;codecs=opus",
                                                      "duration_seconds": 4.2,
                                                      "timing": {"chime_end_ms": 1000, "record_start_ms": 1050, "evil": "x"}})
    assert r.status_code == 200, r.text
    assert student_client.get(base).content == b"AAAABBBB"
    sa = db.scalar(select(SegmentAttempt).where(SegmentAttempt.id == sid))
    assert sa.timing == {"chime_end_ms": 1000, "record_start_ms": 1050} and sa.audio_mime == "audio/webm"
    # One recording per segment (max_record_attempts = 1)
    assert student_client.post(f"{base}/complete", json={"parts": 1}).status_code == 409
    st = student_client.get(f"/api/attempts/{aid}/state").json()
    assert st["dialogues"][0]["segments"][0]["answered"] is True
    assert st["current"]["segment_attempt_id"] == st["dialogues"][0]["segments"][1]["segment_attempt_id"]


def test_submit_marks_skipped_and_queues_scoring(student_client, db):
    d = make_dialogue(db, is_free=True, segments=2)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    sid = first_segment(student_client.get(f"/api/attempts/{aid}/state").json())
    student_client.post(f"/api/attempts/{aid}/segments/{sid}/play")
    files = {"audio": ("a.webm", b"RIFFDATA", "audio/webm")}
    assert student_client.post(f"/api/attempts/{aid}/segments/{sid}/recording", files=files).status_code == 200
    assert student_client.post(f"/api/attempts/{aid}/submit").status_code == 200
    db.expire_all()
    da = db.scalar(select(DialogueAttempt))
    assert da.status == AttemptStatus.COMPLETED and da.submitted_at
    assert [sa.skipped for sa in da.segment_attempts] == [False, True]
    assert db.query(Job).count() == 2
    assert student_client.post(f"/api/attempts/{aid}/segments/{sid}/play").status_code == 409
    assert student_client.post(f"/api/attempts/{aid}/submit").status_code == 409


def test_mock_test_attempt(student_client, db):
    a, b = make_dialogue(db, key="a", segments=2), make_dialogue(db, key="b", segments=3)
    m = make_mock(db, [a, b])
    assert student_client.post("/api/attempts", json={"mock_test_id": str(m.id)}).status_code == 402
    activate(db)
    r = student_client.post("/api/attempts", json={"mock_test_id": str(m.id)}).json()
    assert r["kind"] == "mock"
    st = student_client.get(f"/api/attempts/{r['id']}/state").json()
    assert [len(x["segments"]) for x in st["dialogues"]] == [2, 3] and st["title"] == "Mock 1"
    assert db.scalar(select(MockTestAttempt)).maximum_score == 90
    mocks = student_client.get("/api/mock-tests").json()
    assert mocks[0]["in_progress_id"] == r["id"] and mocks[0]["locked"] is False


def test_attempts_are_private(student_client, db):
    d = make_dialogue(db, is_free=True)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    other = TestClient(app)
    signup(other, email="other@example.com")
    assert other.get(f"/api/attempts/{aid}/state").status_code == 404


def test_dashboard(student_client, db):
    make_dialogue(db, key="free-one", is_free=True)
    make_dialogue(db, key="paid-one")
    dash = student_client.get("/api/dashboard").json()
    assert dash["dialogues_available"] == 1 and dash["dialogues_total"] == 2
    assert dash["quick_start"]["title"] == "Free One" and dash["average_mock_score"] is None
    aid = student_client.post("/api/attempts", json={"dialogue_id": dash["quick_start"]["id"]}).json()["id"]
    dash = student_client.get("/api/dashboard").json()
    assert dash["unfinished"][0]["id"] == aid
