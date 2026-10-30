"""PDF handout per course lesson (client brief: each lesson holds a video, text and a PDF)."""
from app import jobs
from app.models import Lesson
from app.services import lesson_pdf

from .conftest import login, signup
from .factories import make_course

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _upload(admin, lesson_id, data=PDF, name="handout.pdf"):
    return admin.post(f"/api/admin/lessons/{lesson_id}/pdf", files={"file": (name, data, "application/pdf")})


def test_admin_uploads_pdf_and_students_open_it_with_the_lessons_access(client, db):
    course = make_course(db, lessons=2, free_lessons=1)
    free, paid = course.lessons
    login(client, "admin@example.com", "admin-pass-123")
    r = _upload(client, free.id, name="Week 1 notes.pdf")
    assert r.status_code == 200 and r.json()["pdf"]["name"] == "Week-1-notes.pdf"
    assert _upload(client, paid.id).status_code == 200
    assert _upload(client, free.id, data=b"not a pdf").status_code == 400
    assert _upload(client, free.id, name="notes.docx").status_code == 400
    assert client.get(f"/api/admin/lessons/{paid.id}/pdf").content == PDF
    client.post("/api/auth/logout")

    signup(client)  # free plan
    les = client.get(f"/api/lessons/{free.id}").json()
    assert les["pdf"]["url"] == f"/api/lessons/{free.id}/pdf"
    r = client.get(les["pdf"]["url"])
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "private, no-store" and r.headers["content-disposition"].startswith("inline")
    assert client.get(f"/api/lessons/{paid.id}/pdf").status_code == 402  # paid lesson, free plan
    client.post("/api/auth/logout")
    assert client.get(f"/api/lessons/{free.id}/pdf").status_code == 401


def test_remove_pdf(admin_client, db):
    course = make_course(db, lessons=1)
    lid = course.lessons[0].id
    _upload(admin_client, lid)
    assert admin_client.delete(f"/api/admin/lessons/{lid}/pdf").json()["pdf"] is None
    assert admin_client.get(f"/api/admin/lessons/{lid}/pdf").status_code == 404


def test_courses_csv_pdf_url_is_fetched_once(admin_client, db, monkeypatch):
    calls = []

    def fake_download(url, dest):
        calls.append(url)
        dest.write_bytes(PDF)
        return "hash"

    monkeypatch.setattr(lesson_pdf, "download", fake_download)
    csv = (b"course_key,course_title,lesson_no,lesson_title,pdf_url\n"
           b"prep,Prep,1,Lesson 1,https://files.example.com/handouts/lesson1.pdf?sig=abc\n"
           b"prep,Prep,2,Lesson 2,\n")
    for _ in range(2):  # the second import has the same pdf_url: no second download
        job = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", csv, "text/csv")}).json()
        assert job["report"]["ok"], job["report"]
        admin_client.post(f"/api/admin/imports/{job['id']}/commit")
        jobs.run_until_empty()
    assert calls == ["https://files.example.com/handouts/lesson1.pdf?sig=abc"]
    lessons = {lesson.lesson_number: lesson for lesson in db.query(Lesson).all() if lesson.course.key == "prep"}
    db.expire_all()
    assert lessons[1].pdf_name == "lesson1.pdf" and lessons[2].pdf_key == ""
    bad = b"course_key,course_title,lesson_no,lesson_title,pdf_url\nprep,Prep,1,Lesson 1,ftp://x/y.pdf\n"
    rep = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", bad, "text/csv")}).json()["report"]
    assert [e["column"] for e in rep["errors"]] == ["pdf_url"]
