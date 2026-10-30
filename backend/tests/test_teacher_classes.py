"""Teachers' own students and courses: a teacher sees and manages only students they enrolled, who joined through
their link, or whom an admin assigned to them; their courses are shown only to those students."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import User

from .conftest import login, signup
from .test_admin_review import scored_attempt
from .test_scoring_pipeline import answer_audio, reset_mocks  # noqa: F401
from .test_team import make_teacher


def _teacher(db, email):
    make_teacher(db, email)
    c = TestClient(app)
    login(c, email, "teacher-pass-1")
    return c


def _enrol(c, email):
    r = c.post("/api/admin/students", json={"first_name": "Stu", "email": email, "access": "Trial",
                                            "password": "student-pass-1", "send_invite": False})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_teacher_sees_and_manages_only_their_own_students(client, db):
    ann, bob = _teacher(db, "ann@example.com"), _teacher(db, "bob@example.com")
    mine, theirs = _enrol(ann, "a1@example.com"), _enrol(bob, "b1@example.com")
    signup(TestClient(app), email="walkin@example.com")  # no teacher

    assert [s["email"] for s in ann.get("/api/admin/students").json()] == ["a1@example.com"]
    assert ann.get("/api/admin/students").json()[0]["teacher"]["name"] == "Tess Teacher"
    assert ann.get(f"/api/admin/students/{mine}").status_code == 200
    for method, path, body in [("GET", f"/api/admin/students/{theirs}", None),
                               ("GET", f"/api/admin/students/{theirs}/activity", None),
                               ("PATCH", f"/api/admin/students/{theirs}", {"first_name": "X"}),
                               ("POST", f"/api/admin/students/{theirs}/access", {"access": "Active"}),
                               ("POST", f"/api/admin/students/{theirs}/invite", None),
                               ("POST", f"/api/admin/students/{theirs}/password", {"password": "new-pass-123"})]:
        assert ann.request(method, path, json=body).status_code == 404, (method, path)
    # Emails go only to the teacher's own students.
    r = ann.post("/api/admin/students/message", json={"user_ids": [mine, theirs], "subject": "Hi", "body": "Hello"})
    assert r.json() == {"queued": 1, "skipped": 1}
    assert ann.get("/api/admin/overview").json()["students"] == 1
    # A teacher cannot move students between teachers.
    assert ann.patch(f"/api/admin/students/{mine}", json={"teacher_id": None}).status_code == 403

    admin = TestClient(app)
    login(admin, "admin@example.com", "admin-pass-123")
    assert len(admin.get("/api/admin/students").json()) == 3
    assert [s["email"] for s in admin.get("/api/admin/students?teacher=none").json()] == ["walkin@example.com"]
    teachers = {t["email"]: t for t in admin.get("/api/admin/teachers").json()}
    assert teachers["ann@example.com"]["students"] == 1
    # The admin moves Bob's student to Ann.
    r = admin.patch(f"/api/admin/students/{theirs}", json={"teacher_id": teachers["ann@example.com"]["id"]})
    assert r.status_code == 200
    assert {s["email"] for s in ann.get("/api/admin/students").json()} == {"a1@example.com", "b1@example.com"}
    assert bob.get("/api/admin/students").json() == []


def test_admin_enrols_students_for_a_teacher(admin_client, db):
    make_teacher(db, "ann@example.com")
    tid = str(db.scalar(select(User.id).where(User.email == "ann@example.com")))
    r = admin_client.post("/api/admin/students", json={"first_name": "S", "email": "s1@example.com", "password":
                                                       "student-pass-1", "send_invite": False, "teacher_id": tid})
    assert r.status_code == 201
    csv = b"first_name,last_name,email,language,access,access_until,target_exam_date,note\nT,,s2@example.com,,Trial,,,\n"
    r = admin_client.post("/api/admin/students-import", files={"file": ("s.csv", csv, "text/csv")},
                          data={"commit": "true", "send_invites": "false", "teacher_id": tid})
    assert r.status_code == 200, r.text
    rows = db.scalars(select(User).where(User.email.in_(["s1@example.com", "s2@example.com"]))).all()
    assert {str(u.teacher_id) for u in rows} == {tid}
    # Naming someone who is not a teacher is refused.
    me = admin_client.get("/api/me").json()["id"]
    assert admin_client.post("/api/admin/students", json={"first_name": "S", "email": "s3@example.com", "password":
                                                          "student-pass-1", "send_invite": False,
                                                          "teacher_id": me}).status_code == 400


def test_join_link_signup_and_join_while_signed_in(client, db):
    ann = _teacher(db, "ann@example.com")
    link = ann.get("/api/admin/join-link").json()
    assert link["url"].endswith(f"/join/{link['code']}") and link["students"] == 0
    assert ann.get("/api/admin/join-link").json()["code"] == link["code"]  # stable until regenerated

    assert client.get(f"/api/public/join/{link['code']}").json() == {"teacher": "Tess Teacher"}
    assert client.get("/api/public/join/nope").status_code == 404
    me = signup(client, email="new@example.com", teacher_code=link["code"])
    assert me["teacher"] == "Tess Teacher"
    assert [s["email"] for s in ann.get("/api/admin/students").json()] == ["new@example.com"]

    # An existing student without a teacher joins while signed in; joining again is harmless.
    other = TestClient(app)
    signup(other, email="old@example.com")
    assert other.post("/api/me/join", json={"code": link["code"]}).json()["teacher"] == "Tess Teacher"
    assert other.post("/api/me/join", json={"code": link["code"]}).status_code == 200
    # A student who already has a teacher is not moved by another teacher's link.
    bob = _teacher(db, "bob@example.com")
    bob_code = bob.get("/api/admin/join-link").json()["code"]
    assert other.post("/api/me/join", json={"code": bob_code}).status_code == 409
    assert ann.get("/api/admin/join-link").json()["students"] == 2

    # Regenerating stops the old link; students who joined stay.
    new = ann.post("/api/admin/join-link/regenerate").json()["code"]
    assert new != link["code"]
    assert client.get(f"/api/public/join/{link['code']}").status_code == 404
    r = TestClient(app).post("/api/auth/signup", json={"first_name": "L", "email": "late@example.com",
                                                       "password": "student-pass-1", "accept_terms": True,
                                                       "teacher_code": link["code"]})
    assert r.status_code == 400 and "no longer valid" in r.json()["detail"]
    assert len(ann.get("/api/admin/students").json()) == 2

    admin = TestClient(app)
    login(admin, "admin@example.com", "admin-pass-123")
    assert admin.get("/api/admin/join-link").status_code == 400  # links are for teachers


def test_teacher_courses_are_theirs_and_shown_only_to_their_students(client, db):
    ann, bob = _teacher(db, "ann@example.com"), _teacher(db, "bob@example.com")
    r = ann.post("/api/admin/courses", json={"key": "ann-class", "title": "Ann's class", "status": "Published",
                                             "is_free": True})
    assert r.status_code == 201 and r.json()["owner"]["name"] == "Tess Teacher"
    cid = r.json()["id"]
    lesson = ann.post(f"/api/admin/courses/{cid}/lessons", json={"title": "Week 1", "status": "Published"}).json()
    ann.post(f"/api/admin/courses/{cid}/chapters", json={"title": "Part 1"})

    # Ann lists only her own courses; Bob cannot open or change them.
    assert [c["key"] for c in ann.get("/api/admin/courses").json()] == ["ann-class"]
    assert bob.get("/api/admin/courses").json() == []
    assert bob.get(f"/api/admin/courses/{cid}").status_code == 404
    assert bob.patch(f"/api/admin/courses/{cid}", json={"title": "Mine now"}).status_code == 404
    assert bob.patch(f"/api/admin/lessons/{lesson['id']}", json={"title": "x"}).status_code == 404
    chapter = ann.get(f"/api/admin/courses/{cid}").json()["chapters"][0]["id"]
    assert bob.delete(f"/api/admin/chapters/{chapter}").status_code == 404

    admin = TestClient(app)
    login(admin, "admin@example.com", "admin-pass-123")
    assert "ann-class" in [c["key"] for c in admin.get("/api/admin/courses").json()]
    admin_course = admin.post("/api/admin/courses", json={"key": "everyone", "title": "For everyone",
                                                          "status": "Published", "is_free": True}).json()
    assert admin_course["owner"] is None

    code = ann.get("/api/admin/join-link").json()["code"]
    in_class, outside = TestClient(app), TestClient(app)
    signup(in_class, email="in@example.com", teacher_code=code)
    signup(outside, email="out@example.com")
    keys = lambda c: {x["title"] for x in c.get("/api/courses?language=all").json()}  # noqa: E731
    assert {"Ann's class", "For everyone"} <= keys(in_class)
    assert "Ann's class" not in keys(outside) and "For everyone" in keys(outside)
    assert outside.get(f"/api/courses/{cid}").status_code == 404
    assert outside.get(f"/api/lessons/{lesson['id']}").status_code == 404
    assert in_class.get(f"/api/lessons/{lesson['id']}").status_code == 200
    assert "Ann's class" not in keys(bob)  # another teacher does not see it either


def test_teacher_reviews_only_their_students_attempts(client, db, answer_audio):  # noqa: F811
    aid, s1, _ = scored_attempt(db, answer_audio)  # student@example.com, no teacher
    ann = _teacher(db, "ann@example.com")
    assert ann.get(f"/api/admin/attempts/{aid}").status_code == 404
    assert ann.get(f"/api/admin/segment-attempts/{s1}/runs").status_code == 404
    assert ann.post(f"/api/admin/segment-attempts/{s1}/reviewed", json={}).status_code == 404
    assert ann.get("/api/admin/review-queue").json() == []
    assert ann.get("/api/admin/overview").json()["attempts"] == 0

    student = db.scalar(select(User).where(User.email == "student@example.com"))
    student.teacher_id = db.scalar(select(User.id).where(User.email == "ann@example.com"))
    db.commit()
    assert ann.get(f"/api/admin/attempts/{aid}").status_code == 200
    assert ann.get(f"/api/admin/segment-attempts/{s1}/runs").status_code == 200
    assert ann.get("/api/admin/overview").json()["attempts"] == 1
