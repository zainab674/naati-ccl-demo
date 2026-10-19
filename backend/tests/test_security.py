import re
import subprocess

import pytest

from app.main import app
from app.settings import REPO_DIR

from .conftest import signup


def admin_routes():
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/admin"):
            for method in ops:
                yield method.upper(), re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


def test_admin_routes_found():
    assert len(set(admin_routes())) > 25


@pytest.mark.parametrize("method,path", sorted(set(admin_routes())))
def test_every_admin_route_rejects_students(client, method, path):
    assert client.request(method, path).status_code == 401
    signup(client)
    assert client.request(method, path).status_code == 403


def test_cross_site_post_blocked(student_client):
    r = student_client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert student_client.post("/api/auth/logout", headers={"Origin": "http://localhost:3000"}).status_code == 200
    assert student_client.post("/api/auth/logout", headers={"Origin": "http://testserver"}).status_code == 200  # same host


def test_stripe_webhook_exempt_from_origin_check(client):
    r = client.post("/api/stripe/webhook", content=b"{}", headers={"Origin": "https://stripe.example"})
    assert r.status_code != 403  # 503/400 (no secret / bad signature), never the CSRF block


def test_security_headers_and_cookie_flags(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    r = client.post("/api/auth/signup", json={"first_name": "A", "email": "c@example.com", "password": "longenough1",
                                              "accept_terms": True})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_production_settings_are_strict(monkeypatch):
    from app import settings as settings_module

    settings_module.get_settings.cache_clear()
    try:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "short")
        with pytest.raises(RuntimeError):
            settings_module.get_settings()
        settings_module.get_settings.cache_clear()
        monkeypatch.setenv("SECRET_KEY", "x" * 40)
        monkeypatch.setenv("COOKIE_SECURE", "false")
        assert settings_module.get_settings().cookie_secure is True
    finally:
        monkeypatch.undo()
        settings_module.get_settings.cache_clear()
        settings_module.get_settings()


SECRET_PATTERNS = [r"sk_live_[0-9a-zA-Z]{10,}", r"sk_test_[0-9a-zA-Z]{20,}", r"whsec_[0-9a-zA-Z]{20,}",
                   r"gsk_[0-9a-zA-Z]{20,}", r"AIza[0-9A-Za-z_-]{30,}", r"sk-ant-[0-9a-zA-Z_-]{20,}",
                   r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}"]


def test_no_secrets_committed():
    files = subprocess.run(["git", "ls-files"], cwd=REPO_DIR, capture_output=True, text=True, check=True).stdout.split()
    assert ".env" not in files and "backend/.env" not in files
    pattern = re.compile("|".join(SECRET_PATTERNS))
    hits = []
    for f in files:
        path = REPO_DIR / f
        if path.suffix.lower() in (".png", ".ico", ".ts", ".key", ".wav", ".mp3", ".woff2") or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits += [f for _ in pattern.finditer(text)]
    assert hits == []
