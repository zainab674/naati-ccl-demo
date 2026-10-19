from app.models import ContentStatus

from .factories import make_course
from .test_player import activate


def test_course_gating_and_completion(student_client, db):
    c = make_course(db, lessons=3, free_lessons=1)
    make_course(db, key="hidden", status=ContentStatus.DRAFT)
    rows = student_client.get("/api/courses").json()
    assert [r["title"] for r in rows] == ["Intro"] and rows[0]["free_lessons"] == 1 and rows[0]["locked"] is False

    detail = student_client.get(f"/api/courses/{c.id}").json()
    free, paid = detail["lessons"][0], detail["lessons"][1]
    assert free["locked"] is False and paid["locked"] is True

    les = student_client.get(f"/api/lessons/{free['id']}").json()
    assert les["html_content"] == "<p>Lesson 1</p>" and les["next"]["locked"] is True and les["previous"] is None
    assert student_client.get(f"/api/lessons/{paid['id']}").status_code == 402
    assert student_client.post(f"/api/lessons/{paid['id']}/complete").status_code == 402

    assert student_client.post(f"/api/lessons/{free['id']}/complete").json() == {"completed": True}
    student_client.post(f"/api/lessons/{free['id']}/complete")  # idempotent
    assert student_client.get("/api/courses").json()[0]["completed"] == 1
    student_client.delete(f"/api/lessons/{free['id']}/complete")
    assert student_client.get("/api/courses").json()[0]["completed"] == 0

    activate(db)
    assert student_client.get(f"/api/lessons/{paid['id']}").status_code == 200


def test_archived_lessons_hidden(student_client, db):
    c = make_course(db, lessons=2, free_lessons=2)
    c.lessons[1].status = ContentStatus.ARCHIVED
    db.commit()
    detail = student_client.get(f"/api/courses/{c.id}").json()
    assert len(detail["lessons"]) == 1
    assert student_client.get(f"/api/lessons/{c.lessons[1].id}").status_code == 404
