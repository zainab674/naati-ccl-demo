"""Student activity log in the admin (client brief, module 11)."""
from .conftest import login, signup
from .factories import make_course, make_dialogue


def test_activity_log_records_what_the_student_did(client, db):
    d = make_dialogue(db, key="free-1", is_free=True)
    course = make_course(db, lessons=1, free_lessons=1)
    signup(client)
    client.post("/api/auth/logout")
    login(client, "student@example.com", "student-pass-1")
    attempt = client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    client.post("/api/attempts", json={"dialogue_id": str(d.id)})  # resume: not a second "started"
    client.post(f"/api/attempts/{attempt}/submit")
    lesson = course.lessons[0]
    assert client.post(f"/api/lessons/{lesson.id}/complete").status_code == 200
    client.post(f"/api/lessons/{lesson.id}/complete")  # already complete: not logged twice
    me = client.get("/api/me").json()["id"]
    client.post("/api/auth/logout")

    login(client, "admin@example.com", "admin-pass-123")
    log = client.get(f"/api/admin/students/{me}/activity").json()
    kinds = [e["kind"] for e in log]
    assert kinds.count("attempt_started") == 1 and kinds.count("lesson_completed") == 1
    assert {"signup", "login", "attempt_started", "attempt_submitted", "lesson_completed", "email"} <= set(kinds)
    assert [e["at"] for e in log] == sorted((e["at"] for e in log), reverse=True)
    submitted = next(e for e in log if e["kind"] == "attempt_submitted")
    assert submitted["data"]["attempt_id"] == attempt and "0 of 3 segments answered" in submitted["summary"]
    assert next(e for e in log if e["kind"] == "email")["summary"] == "Welcome email"


def test_activity_log_is_staff_only(student_client):
    me = student_client.get("/api/me").json()["id"]
    assert student_client.get(f"/api/admin/students/{me}/activity").status_code == 403
