"""Client's Round 1 revision: cover images, course Start/Resume target, Mock Test statuses, dashboard performance."""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.db import utcnow
from app.main import app
from app.models import AttemptStatus, Dialogue, DialogueAttempt, Difficulty, Topic
from sqlalchemy import select

from .conftest import signup
from .factories import make_dialogue

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _course(admin, key="c1", lessons=2):
    c = admin.post("/api/admin/courses", json={"key": key, "title": "Course", "status": "Published", "is_free": True}).json()
    ids = [admin.post(f"/api/admin/courses/{c['id']}/lessons", json={"title": f"L{i}", "status": "Published"}).json()["id"]
           for i in range(lessons)]
    return c["id"], ids


def test_course_image_upload_serving_and_validation(admin_client):
    cid, _ = _course(admin_client)
    bad = admin_client.post(f"/api/admin/courses/{cid}/image", files={"file": ("x.png", b"<svg/>", "image/png")})
    assert bad.status_code == 400
    r = admin_client.post(f"/api/admin/courses/{cid}/image", files={"file": ("x.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["image_url"].startswith(f"/api/courses/{cid}/image?v=")

    student = TestClient(app)
    signup(student)
    row = next(c for c in student.get("/api/courses?language=all").json() if c["id"] == cid)
    img = student.get(row["image_url"])
    assert img.status_code == 200 and img.content == PNG and img.headers["content-type"] == "image/png"
    assert TestClient(app).get(row["image_url"]).status_code == 401

    # A draft's image is for its editors only.
    admin_client.patch(f"/api/admin/courses/{cid}", json={"status": "Draft"})
    assert student.get(row["image_url"]).status_code == 404
    assert admin_client.get(row["image_url"]).status_code == 200

    assert admin_client.delete(f"/api/admin/courses/{cid}/image").json()["image_url"] is None


def test_resource_image(admin_client):
    r = admin_client.post("/api/admin/resources", json={"key": "r1", "title": "R", "type": "Link",
                                                        "external_url": "https://example.com"}).json()
    done = admin_client.post(f"/api/admin/resources/{r['id']}/image", files={"file": ("x.png", PNG, "image/png")}).json()
    assert admin_client.get(done["image_url"]).content == PNG
    assert admin_client.delete(f"/api/admin/resources/{r['id']}/image").json()["image_url"] is None


def test_start_and_resume_go_to_the_first_unfinished_lesson(admin_client):
    cid, (first, second) = _course(admin_client)
    student = TestClient(app)
    signup(student)
    row = lambda: next(c for c in student.get("/api/courses?language=all").json() if c["id"] == cid)  # noqa: E731
    assert row()["next_lesson"]["id"] == first
    student.post(f"/api/lessons/{first}/complete")
    assert row()["next_lesson"]["id"] == second
    student.post(f"/api/lessons/{second}/complete")
    assert row()["next_lesson"]["id"] == first  # all finished: review from the start


def _attempt(db, user_id, d, score, days_ago):
    db.add(DialogueAttempt(user_id=user_id, dialogue_id=d.id, language_pair_id=d.language_pair_id, total_score=score,
                           status=AttemptStatus.COMPLETED, started_at=utcnow() - timedelta(days=days_ago)))


def test_dashboard_performance_per_topic_and_difficulty(client, db):
    me = signup(client)
    d = make_dialogue(db, key="d1", is_free=True)
    health = db.scalar(select(Topic).where(Topic.name == "Healthcare")) or Topic(name="Healthcare")
    db.add(health)
    db.flush()
    dialogue = db.get(Dialogue, d.id)
    dialogue.topic_id, dialogue.difficulty = health.id, Difficulty.DIFFICULT
    for i, score in enumerate([20, 24, 28, 45]):  # 45 is the oldest, outside the last 3
        _attempt(db, me["id"], d, score, i + 1)
    db.commit()
    dash = client.get("/api/dashboard").json()
    perf = dash["performance"]
    assert perf["difficult_average"] == 24 and perf["easy_average"] is None and perf["total_average"] is None
    row = next(c for c in perf["categories"] if c["topic"] == "Healthcare")
    assert row == {"topic": "Healthcare", "average": 24, "count": 3}
    assert perf["focus"] == [row] and perf["markers"] == {"conditional": 29, "pass": 31.5, "safe": 35}
    assert dash["recent"][0]["outcome"] == "other"

    # The per-dialogue pass line for the "Passed" tab is the marker, not the 29 minimum.
    _attempt(db, me["id"], d, 32, 0)
    db.commit()
    assert client.get("/api/dashboard").json()["recent"][0]["outcome"] == "passed"


def test_dialogue_list_links_review_to_the_latest_finished_attempt(client, db):
    me = signup(client)
    d = make_dialogue(db, key="d1", is_free=True)
    _attempt(db, me["id"], d, 30, 3)
    _attempt(db, me["id"], d, 35, 1)
    db.commit()
    latest = db.scalars(select(DialogueAttempt).where(DialogueAttempt.total_score == 35)).one()
    row = next(x for x in client.get("/api/dialogues?language=all").json() if x["id"] == str(d.id))
    assert row["status"] == "completed" and row["last_attempt_id"] == str(latest.id)
