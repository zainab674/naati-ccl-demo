import pytest

from app.emails import templates
from app.models import EmailLog, EmailStatus
from app.services import email as email_service
from app.settings import get_settings


@pytest.fixture
def settings():
    s = get_settings()
    saved = s.model_dump()
    yield s
    for k, v in saved.items():
        setattr(s, k, v)


@pytest.mark.parametrize("name,ctx", [
    ("welcome", {"first_name": "Sam", "dashboard_url": "http://x/dashboard"}),
    ("password_reset", {"first_name": "Sam", "reset_url": "http://x/reset?token=abc", "expires_minutes": 60}),
    ("receipt", {"first_name": "Sam", "plan_name": "Self-Study", "amount_display": "$99 AUD", "date": "1 Jan 2027",
                 "receipt_url": "https://stripe/x", "dashboard_url": "http://x/dashboard"}),
    ("results_ready", {"first_name": "Sam", "title": "Mock test 1", "total": 64.5, "max": 90, "result": "Pass",
                       "results_url": "http://x/results/1"}),
])
def test_templates_render(name, ctx):
    subject, html, text = templates.render(name, ctx)
    assert subject and "<html>" in html and text
    for v in ctx.values():
        if isinstance(v, str) and v.startswith("http") and not (name == "receipt" and "dashboard" in v):
            assert v in text


def test_templates_escape_html():
    _, html, _ = templates.render("welcome", {"first_name": "<script>x</script>", "dashboard_url": "http://x"})
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_smtp_provider(db, settings, monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["host"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, pw):
            sent["login"] = user

        def send_message(self, msg):
            sent["msg"] = msg

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    settings.email_provider, settings.smtp_host, settings.smtp_user = "smtp", "smtp.example.com", "mailer"
    log = email_service.send_template(db, "welcome", "a@example.com", {"first_name": "A", "dashboard_url": "http://x"})
    assert log.status == EmailStatus.SENT and log.provider == "smtp"
    assert sent["host"] == ("smtp.example.com", 587) and sent["tls"] and sent["login"] == "mailer"
    assert sent["msg"]["To"] == "a@example.com"


def test_resend_provider(db, settings, monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "re_123"}

    calls = {}

    def fake_post(url, json, timeout, headers):
        calls.update(url=url, body=json, auth=headers["Authorization"])
        return Resp()

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    settings.email_provider, settings.resend_api_key = "resend", "re_key"
    log = email_service.send_template(db, "welcome", "b@example.com", {"first_name": "B", "dashboard_url": "http://x"})
    assert log.provider_id == "re_123" and calls["auth"] == "Bearer re_key" and calls["body"]["to"] == ["b@example.com"]


def test_failure_is_logged_not_raised(db, settings, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(email_service.smtplib, "SMTP", boom)
    settings.email_provider, settings.smtp_host = "smtp", "smtp.example.com"
    log = email_service.send_template(db, "welcome", "c@example.com", {"first_name": "C", "dashboard_url": "http://x"})
    assert log.status == EmailStatus.FAILED and "smtp down" in log.error
    assert db.query(EmailLog).filter(EmailLog.to == "c@example.com").count() == 1
