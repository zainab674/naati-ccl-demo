"""Admin Settings: theme (colour, name, logo) and email delivery (SMTP/Resend saved in the database)."""
from sqlalchemy import select

from app.models import PlatformSetting
from app.services import email as email_service
from app.services import platform
from app.services.email import ConsoleProvider

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


# ------------------------------------------------------------------ theme

def test_default_theme_is_the_current_look(client):
    t = client.get("/api/public/theme").json()
    assert t["brand_color"] == "#1f6778" and t["name"] == "Benchmark Education" and t["logo_url"] is None
    assert t["palette"]["600"] == "#1f6778" and t["palette"]["50"] == "#eef7f8"  # matches globals.css


def test_admin_changes_colour_and_name(admin_client):
    r = admin_client.put("/api/admin/settings/theme", json={"brand_color": "#4338CA", "name": "Acme CCL", "tagline": "Practice"})
    assert r.status_code == 200, r.text
    t = admin_client.get("/api/public/theme").json()
    assert (t["brand_color"], t["name"], t["tagline"]) == ("#4338ca", "Acme CCL", "Practice")
    pal = t["palette"]
    assert pal["600"] == "#4338ca" and len(pal) == 11
    # Lighter shades are lighter, darker are darker.
    lum = lambda h: sum(int(h[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
    assert lum(pal["50"]) > lum(pal["300"]) > lum(pal["600"]) > lum(pal["900"])
    # Reset keeps nothing but the logo.
    assert admin_client.post("/api/admin/settings/theme/reset").json()["name"] == "Benchmark Education"


def test_unreadable_colour_and_markup_are_rejected(admin_client):
    r = admin_client.put("/api/admin/settings/theme", json={"brand_color": "#ffe066"})
    assert r.status_code == 400 and "too light" in r.json()["detail"]
    assert admin_client.put("/api/admin/settings/theme", json={"name": "<script>x</script>"}).status_code == 400
    assert admin_client.put("/api/admin/settings/theme", json={"brand_color": "red"}).status_code == 422


def test_logo_upload_and_serving(admin_client, client):
    r = admin_client.post("/api/admin/settings/theme/logo", files={"file": ("logo.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    url = client.get("/api/public/theme").json()["logo_url"]
    img = client.get(url)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content == PNG
    bad = admin_client.post("/api/admin/settings/theme/logo", files={"file": ("x.svg", b"<svg onload=alert(1)>", "image/svg+xml")})
    assert bad.status_code == 400
    admin_client.delete("/api/admin/settings/theme/logo")
    assert client.get("/api/public/theme").json()["logo_url"] is None


def test_emails_use_the_platform_name_and_colour(admin_client, db):
    admin_client.put("/api/admin/settings/theme", json={"brand_color": "#4338ca", "name": "Acme CCL"})
    ConsoleProvider.outbox.clear()
    admin_client.post("/api/admin/settings/email/test", json={"to": "me@example.com"})
    msg = ConsoleProvider.outbox[-1]
    assert msg.subject.startswith("Acme CCL") and "#4338ca" in msg.html


def test_theme_settings_are_admin_only(student_client):
    assert student_client.put("/api/admin/settings/theme", json={"name": "x"}).status_code == 403
    assert student_client.get("/api/admin/settings/email").status_code == 403


# ------------------------------------------------------------------ email

SMTP_BODY = {"provider": "smtp", "email_from": "Acme <no-reply@acme.example>", "reply_to": "help@acme.example",
             "smtp_host": "smtp.acme.example", "smtp_port": 465, "smtp_user": "mailer", "smtp_security": "ssl",
             "smtp_password": "s3cret-pass"}


def test_smtp_settings_saved_encrypted_and_never_returned(admin_client, db):
    assert admin_client.get("/api/admin/settings/email").json()["source"] == "env"
    r = admin_client.put("/api/admin/settings/email", json=SMTP_BODY).json()
    assert r["smtp_password_set"] is True and "s3cret-pass" not in str(r) and r["source"] == "settings"
    row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == "email"))
    assert "s3cret-pass" not in str(row.value) and platform.decrypt(row.value["smtp_password_enc"]) == "s3cret-pass"
    # Saving again without a password keeps it; an empty string clears it.
    assert admin_client.put("/api/admin/settings/email", json={**SMTP_BODY, "smtp_password": None}).json()["smtp_password_set"]
    assert not admin_client.put("/api/admin/settings/email", json={**SMTP_BODY, "smtp_password": ""}).json()["smtp_password_set"]


def test_saved_smtp_settings_are_used_for_sending(admin_client, db, monkeypatch):
    sent = {}

    class FakeSSL:
        def __init__(self, host, port, timeout):
            sent["host"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["starttls"] = True
        def login(self, u, p): sent["login"] = (u, p)
        def send_message(self, m): sent["from"], sent["reply"] = m["From"], m["Reply-To"]

    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSSL)
    admin_client.put("/api/admin/settings/email", json=SMTP_BODY)
    r = admin_client.post("/api/admin/settings/email/test", json={"to": "me@example.com"}).json()
    assert r == {"ok": True, "provider": "smtp", "error": ""}
    assert sent == {"host": ("smtp.acme.example", 465), "login": ("mailer", "s3cret-pass"),
                    "from": "Acme <no-reply@acme.example>", "reply": "help@acme.example"}  # SSL: no STARTTLS


def test_test_email_reports_the_provider_error(admin_client, monkeypatch):
    def refused(*a, **k):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(email_service.smtplib, "SMTP", refused)
    admin_client.put("/api/admin/settings/email", json={**SMTP_BODY, "smtp_port": 587, "smtp_security": "starttls"})
    r = admin_client.post("/api/admin/settings/email/test", json={"to": "me@example.com"}).json()
    assert r["ok"] is False and "connection refused" in r["error"]


def test_email_settings_validation_and_reset(admin_client, db):
    assert admin_client.put("/api/admin/settings/email", json={**SMTP_BODY, "smtp_host": ""}).status_code == 400
    assert admin_client.put("/api/admin/settings/email", json={**SMTP_BODY, "provider": "pigeon"}).status_code == 400
    assert admin_client.put("/api/admin/settings/email", json={**SMTP_BODY, "email_from": "a@b.c\r\nBcc: x@y.z"}).status_code == 400
    admin_client.put("/api/admin/settings/email", json=SMTP_BODY)
    assert admin_client.post("/api/admin/settings/email/reset").json()["source"] == "env"


def test_changed_secret_key_is_reported_not_crashing(admin_client, monkeypatch):
    from cryptography.fernet import Fernet

    admin_client.put("/api/admin/settings/email", json=SMTP_BODY)
    # As if SECRET_KEY changed: the saved token no longer decrypts (sessions are left alone here).
    other = Fernet(Fernet.generate_key())
    monkeypatch.setattr(platform, "_fernet", lambda: other)
    r = admin_client.get("/api/admin/settings/email").json()
    assert r["smtp_password_set"] is False and "could not be decrypted" in r["problem"]
    assert admin_client.post("/api/admin/settings/email/test", json={"to": "me@example.com"}).status_code == 200
