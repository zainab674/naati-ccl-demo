"""Client's Learning Hub fields: Course at a Glance, lesson Notes and length; new accounts on the admin overview."""
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import utcnow
from app.main import app
from app.models import Course, User
from app.services.imports import courses as course_import

from .conftest import signup


def _course(admin):
    c = admin.post("/api/admin/courses", json={"key": "c1", "title": "Course", "status": "Published", "is_free": True}).json()
    lesson = admin.post(f"/api/admin/courses/{c['id']}/lessons", json={"title": "L1", "status": "Published"}).json()
    return c["id"], lesson["id"]


def test_at_a_glance_is_sanitised_and_shown_to_students(admin_client):
    cid, _ = _course(admin_client)
    r = admin_client.patch(f"/api/admin/courses/{cid}", json={"at_a_glance_html": "<ul><li>Self-paced</li></ul><script>x()</script>"})
    assert r.json()["at_a_glance_html"] == "<ul><li>Self-paced</li></ul>"
    student = TestClient(app)
    signup(student)
    assert student.get(f"/api/courses/{cid}").json()["at_a_glance_html"] == "<ul><li>Self-paced</li></ul>"
    # Saving another field leaves it in place.
    r = admin_client.patch(f"/api/admin/courses/{cid}", json={"title": "New title"})
    assert r.json()["at_a_glance_html"] == "<ul><li>Self-paced</li></ul>"


def test_at_a_glance_is_sanitised_on_create(admin_client):
    r = admin_client.post("/api/admin/courses", json={"key": "c2", "title": "C", "at_a_glance_html": "<p onclick='x()'>Hi</p>"})
    assert r.status_code == 201 and "onclick" not in r.json()["at_a_glance_html"]


def test_lesson_notes_and_duration(admin_client):
    cid, lid = _course(admin_client)
    r = admin_client.patch(f"/api/admin/lessons/{lid}", json={"notes_html": "<p>Remember</p><script>x()</script>", "duration_minutes": 90})
    assert r.json()["notes_html"] == "<p>Remember</p>" and r.json()["duration_minutes"] == 90
    assert admin_client.patch(f"/api/admin/lessons/{lid}", json={"duration_minutes": 0}).status_code == 422

    student = TestClient(app)
    signup(student)
    body = student.get(f"/api/lessons/{lid}").json()
    assert body["notes_html"] == "<p>Remember</p>" and body["duration_minutes"] == 90
    outline = student.get(f"/api/courses/{cid}").json()
    assert outline["duration_minutes"] == 90 and outline["chapters"][0]["duration_minutes"] == 90
    assert outline["lessons"][0]["duration_minutes"] == 90
    row = next(c for c in student.get("/api/courses?language=all").json() if c["id"] == cid)
    assert row["duration_minutes"] == 90

    admin_client.patch(f"/api/admin/lessons/{lid}", json={"duration_minutes": None})
    assert student.get(f"/api/courses/{cid}").json()["duration_minutes"] is None


def test_notes_stay_behind_the_paid_lock(admin_client):
    c = admin_client.post("/api/admin/courses", json={"key": "paid", "title": "Paid", "status": "Published"}).json()
    lesson = admin_client.post(f"/api/admin/courses/{c['id']}/lessons",
                               json={"title": "L", "status": "Published", "notes_html": "<p>Paid notes</p>"}).json()
    student = TestClient(app)
    signup(student)
    assert student.get(f"/api/lessons/{lesson['id']}").status_code == 402
    assert "Paid notes" not in student.get(f"/api/courses/{c['id']}").text


def test_csv_sets_new_fields_and_blank_columns_keep_them(admin_client, db):
    header = "course_key,course_title,lesson_no,lesson_title,course_at_a_glance,lesson_notes,duration_minutes\n"
    data = (header + 'c9,Course,1,L1,"<p>Glance</p>","<p>Notes</p>",25\nc9,Course,2,L2,,,\n').encode()
    report, parsed = course_import.parse(db, data)
    assert not report.errors
    course_import.commit(db, parsed)
    course = db.scalar(select(Course).where(Course.key == "c9"))
    assert course.at_a_glance_html == "<p>Glance</p>"
    assert (course.lessons[0].notes_html, course.lessons[0].duration_minutes) == ("<p>Notes</p>", 25)

    report, parsed = course_import.parse(db, b"course_key,course_title,lesson_no,lesson_title\nc9,Course,1,L1\nc9,Course,2,L2\n")
    course_import.commit(db, parsed)
    db.expire_all()
    course = db.scalar(select(Course).where(Course.key == "c9"))
    assert course.at_a_glance_html == "<p>Glance</p>"
    assert (course.lessons[0].notes_html, course.lessons[0].duration_minutes) == ("<p>Notes</p>", 25)


def test_csv_rejects_a_bad_duration(db):
    report, _ = course_import.parse(db, b"course_key,course_title,lesson_no,lesson_title,duration_minutes\nc9,C,1,L,soon\n")
    assert any(e["column"] == "duration_minutes" for e in report.as_dict()["errors"])


def test_new_accounts_counts_recent_students(admin_client, db):
    assert admin_client.get("/api/admin/overview").json()["new_accounts"] == 0
    other = TestClient(app)
    signup(other)
    overview = admin_client.get("/api/admin/overview").json()
    assert overview["new_accounts"] == 1 and overview["new_accounts_days"] == 30
    user = db.scalar(select(User).where(User.email == "student@example.com"))
    user.created_at = utcnow() - timedelta(days=31)
    db.commit()
    assert admin_client.get("/api/admin/overview").json()["new_accounts"] == 0
