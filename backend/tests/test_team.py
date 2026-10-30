"""Teacher role (client brief, module 11): teachers use the student, enrolment and review screens only."""
import pytest
from sqlalchemy import select

from app.models import User, UserRole
from app.security import hash_password

from .conftest import login, signup
from .test_security import admin_routes

# Routes a teacher may use. Everything else under /api/admin is admins only.
TEACHER_PREFIXES = ("/api/admin/overview", "/api/admin/students", "/api/admin/attempts", "/api/admin/review",
                    "/api/admin/segment-attempts")


def make_teacher(db, email="teacher@example.com"):
    db.add(User(first_name="Tess", last_name="Teacher", email=email, role=UserRole.TEACHER,
                password_hash=hash_password("teacher-pass-1")))
    db.commit()


@pytest.fixture
def teacher_client(client, db):
    make_teacher(db)
    login(client, "teacher@example.com", "teacher-pass-1")
    return client


@pytest.mark.parametrize("method,path", sorted(set(admin_routes())))
def test_teacher_reaches_only_student_and_review_routes(teacher_client, method, path):
    status = teacher_client.request(method, path).status_code
    if path.startswith(TEACHER_PREFIXES):
        assert status not in (401, 403), (method, path, status)
    else:
        assert status == 403, (method, path, status)


def test_teacher_can_enrol_and_list_students(teacher_client):
    r = teacher_client.post("/api/admin/students", json={"first_name": "Dana", "email": "dana@example.com",
                                                         "access": "Trial", "password": "student-pass-1",
                                                         "send_invite": False})
    assert r.status_code == 201, r.text
    assert [s["email"] for s in teacher_client.get("/api/admin/students").json()] == ["dana@example.com"]
    assert teacher_client.get("/api/me").json()["role"] == "teacher"


def test_admin_adds_teacher_with_invite_and_changes_role(admin_client, db):
    r = admin_client.post("/api/admin/team", json={"first_name": "Tess", "email": "Tess@Example.com", "role": "teacher"})
    assert r.status_code == 201 and r.json()["invited"] and r.json()["email"] == "tess@example.com"
    assert admin_client.post("/api/admin/team", json={"first_name": "T", "email": "tess@example.com"}).status_code == 409
    assert {m["email"]: m["role"] for m in admin_client.get("/api/admin/team").json()} == {
        "admin@example.com": "admin", "tess@example.com": "teacher"}
    tid = r.json()["id"]
    assert admin_client.patch(f"/api/admin/team/{tid}", json={"role": "admin"}).json()["role"] == "admin"
    assert admin_client.patch(f"/api/admin/team/{tid}", json={"role": "boss"}).status_code == 400
    assert admin_client.patch(f"/api/admin/team/{tid}", json={"role": "student"}).json()["role"] == "student"
    assert admin_client.patch(f"/api/admin/team/{tid}", json={"is_active": False}).status_code == 404  # left the team


def test_admin_promotes_existing_student_without_invite(client, db):
    signup(client, email="sam@example.com")
    client.post("/api/auth/logout")
    login(client, "admin@example.com", "admin-pass-123")
    r = client.post("/api/admin/team", json={"first_name": "Sam", "email": "sam@example.com", "role": "teacher"})
    assert r.status_code == 201 and not r.json()["invited"]
    assert db.scalar(select(User).where(User.email == "sam@example.com")).role == UserRole.TEACHER


def test_admin_cannot_change_own_role(admin_client, db):
    me = admin_client.get("/api/me").json()["id"]
    assert admin_client.patch(f"/api/admin/team/{me}", json={"role": "teacher"}).status_code == 400


def test_deactivated_teacher_is_signed_out(client, db):
    make_teacher(db)
    login(client, "admin@example.com", "admin-pass-123")
    tid = next(m["id"] for m in client.get("/api/admin/team").json() if m["role"] == "teacher")
    assert client.patch(f"/api/admin/team/{tid}", json={"is_active": False}).json()["is_active"] is False
    r = client.post("/api/auth/login", json={"email": "teacher@example.com", "password": "teacher-pass-1"})
    assert r.status_code in (401, 403)
