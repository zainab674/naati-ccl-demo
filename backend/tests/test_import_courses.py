from sqlalchemy import select

from app.models import ContentStatus, Course, Lesson
from app.services.imports import samples

H = samples.COURSES_HEADER


def upload(client, text):
    r = client.post("/api/admin/imports/courses", files={"file": ("c.csv", text.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def commit(client, job):
    return client.post(f"/api/admin/imports/{job['id']}/commit").json()


def test_sample_course_file(admin_client):
    job = upload(admin_client, samples.COURSES_SAMPLE)
    assert job["status"] == "Validated", job["report"]
    assert job["report"]["summary"]["lessons"] == 2


def test_course_validation_errors(admin_client, db):
    text = "\n".join([H,
                      "intro,Intro,,1,Lesson 1,,<p>a</p>,true",
                      "intro,Intro,,1,Dup,,,false",            # duplicate lesson_no
                      "intro,Intro,,x,Bad number,,,false",     # bad lesson_no
                      "intro,Other title,,2,L2,,,false",       # inconsistent course title
                      "intro,Intro,,3,L3,not-a-url,,false",    # bad video url
                      "intro,Intro,,4,L4,,,maybe",             # bad bool
                      "Bad Key!,Intro,,1,L,,,false"]) + "\n"
    job = upload(admin_client, text)
    assert job["status"] == "Invalid"
    cols = {(e["row"], e["column"]) for e in job["report"]["errors"]}
    assert {(3, "lesson_no"), (4, "lesson_no"), (5, "course_title"), (6, "video_url"), (7, "is_free"),
            (8, "course_key")} <= cols
    assert db.query(Course).count() == 0


def test_course_commit_sanitises_and_is_idempotent(admin_client, db):
    text = "\n".join([H,
                      'ccl-prep,Exam Preparation,Prep course,1,Overview,https://www.youtube.com/embed/x,'
                      '"<p onclick=""x()"">Hi<script>alert(1)</script></p>",true',
                      "ccl-prep,Exam Preparation,Prep course,2,Numbers,,<p>Numbers</p>,false"]) + "\n"
    job = upload(admin_client, text)
    assert job["status"] == "Validated"
    assert any(w["column"] == "html_content" for w in job["report"]["warnings"])
    done = commit(admin_client, job)
    assert done["status"] == "Completed" and done["counts"]["lessons_created"] == 2
    course = db.scalar(select(Course).where(Course.key == "ccl-prep"))
    assert course.status == ContentStatus.DRAFT and course.is_free is False
    first = course.lessons[0]
    assert "<script>" not in first.html_content and "onclick" not in first.html_content and first.is_free

    again = commit(admin_client, upload(admin_client, text))
    assert again["counts"] == {"courses_created": 0, "courses_updated": 0, "lessons_created": 0,
                               "lessons_updated": 0, "lessons_archived": 0}

    shorter = "\n".join([H, "ccl-prep,Exam Preparation,Prep course,1,Overview v2,,<p>New</p>,true"]) + "\n"
    third = commit(admin_client, upload(admin_client, shorter))
    assert third["counts"]["lessons_updated"] == 1 and third["counts"]["lessons_archived"] == 1
    db.expire_all()
    assert db.query(Lesson).count() == 2
    assert db.scalar(select(Lesson).where(Lesson.lesson_number == 2)).status == ContentStatus.ARCHIVED
