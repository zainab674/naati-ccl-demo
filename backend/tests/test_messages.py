"""Admins and teachers email one or many students (client brief, module 11)."""
from sqlalchemy import select

from app import jobs
from app.models import EmailLog, User
from app.services.email import ConsoleProvider

from .conftest import login, signup


def _students(client, *emails):
    for e in emails:
        signup(client, email=e)
        client.post("/api/auth/logout")
    login(client, "admin@example.com", "admin-pass-123")
    return {s["email"]: s["id"] for s in client.get("/api/admin/students").json()}


def test_message_many_students_personalised_and_logged(client, db):
    ids = _students(client, "a@example.com", "b@example.com")
    ConsoleProvider.outbox.clear()
    r = client.post("/api/admin/students/message", json={
        "user_ids": list(ids.values()), "subject": "Mock test tips for {first_name}",
        "body": "Hi {first_name},\n\nRemember to check your microphone.\nGood luck!"})
    assert r.json() == {"queued": 2, "skipped": 0}
    jobs.run_until_empty()
    sent = {m.to: m for m in ConsoleProvider.outbox}
    assert set(sent) == {"a@example.com", "b@example.com"}
    assert sent["a@example.com"].subject == "Mock test tips for Sam"
    assert "Hi Sam," in sent["a@example.com"].text and "<br>" in sent["a@example.com"].html
    assert "From " in sent["a@example.com"].text
    logs = db.scalars(select(EmailLog).where(EmailLog.template == "message")).all()
    assert len(logs) == 2 and all(e.user_id for e in logs)
    detail = client.get(f"/api/admin/students/{ids['a@example.com']}").json()
    assert detail["emails"][0]["subject"] == "Mock test tips for Sam"


def test_message_escapes_html_and_skips_inactive(client, db):
    ids = _students(client, "a@example.com", "b@example.com")
    db.scalar(select(User).where(User.email == "b@example.com")).is_active = False
    db.commit()
    ConsoleProvider.outbox.clear()
    r = client.post("/api/admin/students/message", json={"user_ids": list(ids.values()), "subject": "Hello",
                                                          "body": "<script>alert(1)</script>"})
    assert r.json() == {"queued": 1, "skipped": 1}
    jobs.run_until_empty()
    [m] = ConsoleProvider.outbox
    assert "<script>" not in m.html and "&lt;script&gt;" in m.html


def test_message_needs_subject_body_and_recipients(admin_client):
    assert admin_client.post("/api/admin/students/message", json={"user_ids": [], "subject": "x", "body": "y"}).status_code == 400
    assert admin_client.post("/api/admin/students/message",
                             json={"user_ids": ["00000000-0000-0000-0000-000000000000"], "subject": " ", "body": "y"}
                             ).status_code == 400
