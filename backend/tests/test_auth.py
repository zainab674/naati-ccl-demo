import re

from sqlalchemy import select

from app.models import EmailLog, User
from app.services.email import ConsoleProvider

from .conftest import login, signup


def test_signup_login_logout(client, db):
    u = signup(client, email="New@Example.com")
    assert u["email"] == "new@example.com"
    assert u["role"] == "student" and u["has_active_plan"] is False
    assert client.get("/api/me").json()["email"] == "new@example.com"
    # welcome email logged
    log = db.scalar(select(EmailLog).where(EmailLog.to == "new@example.com"))
    assert log.template == "welcome" and log.status.value == "sent"

    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    login(client, "new@example.com", "student-pass-1")
    assert client.get("/api/me").status_code == 200


def test_signup_validation(client):
    signup(client)
    r = client.post("/api/auth/signup", json={"first_name": "A", "email": "student@example.com",
                                               "password": "longenough", "accept_terms": True})
    assert r.status_code == 409
    r = client.post("/api/auth/signup", json={"first_name": "A", "email": "x@example.com", "password": "short",
                                               "accept_terms": True})
    assert r.status_code == 422
    r = client.post("/api/auth/signup", json={"first_name": "A", "email": "y@example.com",
                                               "password": "longenough", "accept_terms": False})
    assert r.status_code == 400


def test_wrong_password_and_rate_limit(client):
    signup(client)
    client.post("/api/auth/logout")
    codes = [client.post("/api/auth/login", json={"email": "student@example.com", "password": "nope"}).status_code
             for _ in range(12)]
    assert codes[0] == 401
    assert 429 in codes


def test_password_reset_flow(client, db):
    signup(client)
    client.post("/api/auth/logout")
    assert client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json() == {"ok": True}
    assert client.post("/api/auth/forgot-password", json={"email": "student@example.com"}).json() == {"ok": True}
    msg = ConsoleProvider.outbox[-1]
    assert msg.to == "student@example.com"
    token = re.search(r"token=([\w-]+)", msg.text).group(1)

    r = client.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
    assert r.status_code == 200
    # token is single use
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "another-pass"}).status_code == 400
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "student@example.com",
                                                "password": "student-pass-1"}).status_code == 401
    login(client, "student@example.com", "brand-new-pass")


def test_reset_invalidates_old_sessions(client, db):
    from fastapi.testclient import TestClient

    from app.main import app

    signup(client)
    old_cookie = client.cookies.get("ccl_session")
    client.post("/api/auth/forgot-password", json={"email": "student@example.com"})
    token = re.search(r"token=([\w-]+)", ConsoleProvider.outbox[-1].text).group(1)
    with TestClient(app) as other:
        other.post("/api/auth/reset-password", json={"token": token, "password": "brand-new-pass"})
    stale = TestClient(app)
    stale.cookies.set("ccl_session", old_cookie)
    assert stale.get("/api/me").status_code == 401


def test_admin_role_and_profile(client, db):
    login(client, "admin@example.com", "admin-pass-123")
    me = client.get("/api/me").json()
    assert me["role"] == "admin" and me["has_active_plan"] is True
    r = client.patch("/api/me", json={"first_name": "Ada", "target_exam_date": "2027-02-01"})
    assert r.json()["first_name"] == "Ada" and r.json()["target_exam_date"] == "2027-02-01"
    assert db.scalar(select(User).where(User.email == "admin@example.com")).last_login_at is not None
