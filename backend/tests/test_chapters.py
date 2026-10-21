"""Course chapters: admin management, the student outline (2.1 numbering, reading order), CSV import."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import CourseChapter

from .conftest import signup
from .factories import make_course
from .test_player import activate


def _setup(admin, db):
    """Course with 4 lessons: chapters "Overview" (lessons 1, 2) and "Skills" (lesson 3); lesson 4 has no chapter."""
    c = make_course(db, key="exam", lessons=4, free_lessons=4)
    admin.post(f"/api/admin/courses/{c.id}/chapters", json={"title": "Overview"})
    data = admin.post(f"/api/admin/courses/{c.id}/chapters", json={"title": "Skills"}).json()
    ch = {x["title"]: x["id"] for x in data["chapters"]}
    lessons = {x["lesson_number"]: x["id"] for x in data["lessons"]}
    for n, title in [(1, "Overview"), (2, "Overview"), (3, "Skills")]:
        r = admin.patch(f"/api/admin/lessons/{lessons[n]}", json={"chapter_id": ch[title]})
        assert r.status_code == 200, r.text
    return c, ch, lessons


def test_student_outline_groups_and_numbers_lessons(admin_client, db):
    c, ch, lessons = _setup(admin_client, db)
    student = TestClient(app)
    signup(student)
    data = student.get(f"/api/courses/{c.id}").json()
    assert [(g["number"], g["title"], [x["number"] for x in g["lessons"]]) for g in data["chapters"]] == [
        (1, "Overview", ["1.1", "1.2"]), (2, "Skills", ["2.1"]), (None, None, ["1"])]
    les = student.get(f"/api/lessons/{lessons[3]}").json()
    assert les["number"] == "2.1" and les["chapter"] == {"number": 2, "title": "Skills"}
    # Previous / Next follow the outline.
    assert les["previous"]["id"] == lessons[2] and les["next"]["id"] == lessons[4]


def test_reordering_chapters_changes_reading_order(admin_client, db):
    c, ch, lessons = _setup(admin_client, db)
    admin_client.patch(f"/api/admin/chapters/{ch['Skills']}", json={"move": "up"})
    student = TestClient(app)
    signup(student)
    activate(db)
    order = [x["number"] + " " + x["id"] for x in student.get(f"/api/courses/{c.id}").json()["lessons"]]
    assert [o.split()[1] for o in order] == [lessons[3], lessons[1], lessons[2], lessons[4]]
    assert [o.split()[0] for o in order] == ["1.1", "2.1", "2.2", "1"]


def test_deleting_a_chapter_keeps_its_lessons(admin_client, db):
    c, ch, lessons = _setup(admin_client, db)
    data = admin_client.delete(f"/api/admin/chapters/{ch['Overview']}").json()
    assert [x["title"] for x in data["chapters"]] == ["Skills"]
    assert len(data["lessons"]) == 4
    assert {x["id"]: x["chapter_id"] for x in data["lessons"]}[lessons[1]] is None


def test_chapter_from_another_course_is_rejected(admin_client, db):
    a, b = make_course(db, key="a-course"), make_course(db, key="b-course")
    other = admin_client.post(f"/api/admin/courses/{b.id}/chapters", json={"title": "B1"}).json()["chapters"][0]["id"]
    lesson = admin_client.get(f"/api/admin/courses/{a.id}").json()["lessons"][0]["id"]
    assert admin_client.patch(f"/api/admin/lessons/{lesson}", json={"chapter_id": other}).status_code == 400


CSV = (b"course_key,course_title,lesson_no,lesson_title,chapter_no,chapter_title\n"
       b"prep,Exam prep,1,What is CCL,1,CCL Test Overview\n"
       b"prep,Exam prep,2,Format,1,\n"
       b"prep,Exam prep,3,Meaning units,2,Interpreting Skills\n")


def test_course_csv_with_chapters(admin_client, db):
    job = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", CSV, "text/csv")}).json()
    assert job["report"]["ok"], job["report"]
    assert job["report"]["summary"]["chapters"] == 2
    admin_client.post(f"/api/admin/imports/{job['id']}/commit")
    cid = next(c["id"] for c in admin_client.get("/api/admin/courses").json() if c["key"] == "prep")
    data = admin_client.get(f"/api/admin/courses/{cid}").json()
    assert [(x["number"], x["title"]) for x in data["chapters"]] == [(1, "CCL Test Overview"), (2, "Interpreting Skills")]
    assert [x["number"] for x in data["lessons"]] == ["1.1", "1.2", "2.1"]
    # Re-import without chapter 2: the chapter goes, its lesson stays (chapterless).
    again = CSV.replace(b"3,Meaning units,2,Interpreting Skills", b"3,Meaning units,,")
    job = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", again, "text/csv")}).json()
    admin_client.post(f"/api/admin/imports/{job['id']}/commit")
    db.expire_all()
    assert [ch.title for ch in db.scalars(select(CourseChapter))] == ["CCL Test Overview"]


def test_course_csv_chapter_errors(admin_client):
    bad = (b"course_key,course_title,lesson_no,lesson_title,chapter_no,chapter_title\n"
           b"prep,Exam prep,1,A,x,Ch\n"
           b"prep,Exam prep,2,B,2,\n"
           b"prep,Exam prep,3,C,,Orphan title\n")
    rep = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", bad, "text/csv")}).json()["report"]
    assert sorted((e["row"], e["column"]) for e in rep["errors"]) == [(2, "chapter_no"), (3, "chapter_title"), (4, "chapter_no")]
