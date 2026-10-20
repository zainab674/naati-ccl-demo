"""Learning hub (MVP_SPEC module 15): admin management, private files, free/paid gating, language filter."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import get_storage

from .conftest import signup
from .test_player import activate

PDF = b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _new(admin, **kw):
    body = {"key": "glossary-health", "title": "Health glossary", "type": "Ebook", **kw}
    r = admin.post("/api/admin/resources", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _upload(admin, rid, name="Glossary Ñ.pdf", data=PDF):
    return admin.post(f"/api/admin/resources/{rid}/file", files={"file": (name, data, "application/octet-stream")})


def _student(email="s@example.com", **kw):
    c = TestClient(app)
    signup(c, email=email, **kw)
    return c


def test_publish_needs_matching_content(admin_client):
    rid = _new(admin_client)["id"]
    r = admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Published"})
    assert r.status_code == 400 and "needs an uploaded file" in r.json()["detail"]
    up = _upload(admin_client, rid).json()
    assert up["file_name"] == "Glossary-N.pdf" and up["content_type"] == "application/pdf" and up["problems"] == []
    assert admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Published"}).json()["status"] == "Published"
    link = _new(admin_client, key="naati-site", title="NAATI CCL page", type="Link")["id"]
    assert admin_client.patch(f"/api/admin/resources/{link}", json={"external_url": "ftp://x", "status": "Published"}).status_code == 400
    assert admin_client.patch(f"/api/admin/resources/{link}",
                              json={"external_url": "https://www.naati.com.au", "status": "Published"}).status_code == 200


def test_upload_rejects_wrong_or_disguised_files(admin_client):
    rid = _new(admin_client)["id"]
    assert "not allowed" in _upload(admin_client, rid, "notes.html", b"<script>").json()["detail"]
    assert "does not look like" in _upload(admin_client, rid, "evil.pdf", b"<html><script>alert(1)</script>").json()["detail"]
    assert _upload(admin_client, rid, "empty.pdf", b"").status_code == 400


def test_upload_size_limit(admin_client, monkeypatch):
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "resource_max_mb", 1)
    rid = _new(admin_client)["id"]
    assert _upload(admin_client, rid, data=PDF + b"0" * (1024 * 1024)).status_code == 413


def test_paid_file_is_locked_until_the_student_has_a_plan(admin_client, db):
    rid = _new(admin_client)["id"]
    _upload(admin_client, rid)
    admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Published"})
    student = _student()
    row = student.get("/api/resources").json()[0]
    assert row["locked"] and row["type"] == "Ebook" and "file_key" not in row
    assert student.get(f"/api/resources/{rid}").status_code == 402
    assert student.get(f"/api/resources/{rid}/file").status_code == 402
    activate(db, "s@example.com")
    detail = student.get(f"/api/resources/{rid}").json()
    assert detail["file_url"] == f"/api/resources/{rid}/file" and not detail["locked"]
    f = student.get(detail["file_url"])
    assert f.status_code == 200 and f.content == PDF and f.headers["content-type"] == "application/pdf"
    assert f.headers["content-disposition"].startswith("inline;") and "no-store" in f.headers["cache-control"]
    assert f.headers["x-frame-options"] == "SAMEORIGIN"  # the hub page shows the PDF in an iframe
    assert TestClient(app).get(f"/api/resources/{rid}/file").status_code == 401  # signed out


def test_free_article_is_sanitised_and_open(admin_client):
    rid = _new(admin_client, key="tips", title="Note-taking tips", type="Article", is_free=True,
               html_content='<p>Use symbols</p><script>alert(1)</script><img src=x onerror="alert(1)">')["id"]
    admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Published"})
    detail = _student().get(f"/api/resources/{rid}").json()
    assert "<script" not in detail["html_content"] and "onerror" not in detail["html_content"]
    assert "<p>Use symbols</p>" in detail["html_content"]


def test_drafts_are_hidden_from_students(admin_client):
    rid = _new(admin_client)["id"]
    _upload(admin_client, rid)
    student = _student()
    assert student.get("/api/resources").json() == []
    assert student.get(f"/api/resources/{rid}/file").status_code == 404
    assert admin_client.get(f"/api/admin/resources/{rid}/file").content == PDF  # admin preview


def test_language_and_type_filters(admin_client):
    for key, lang, kind in [("all-1", None, "Link"), ("hi-1", "hi", "Link"), ("ar-1", "ar", "Glossary")]:
        rid = _new(admin_client, key=key, title=key, type=kind, language=lang, external_url="https://example.com/x",
                   is_free=True)["id"]
        assert admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Published"}).status_code == 200
    student = _student(language="hi")
    assert {r["title"] for r in student.get("/api/resources").json()} == {"all-1", "hi-1"}
    assert {r["title"] for r in student.get("/api/resources?language=all").json()} == {"all-1", "hi-1", "ar-1"}
    assert [r["title"] for r in student.get("/api/resources?language=all&type=Glossary").json()] == ["ar-1"]
    assert student.get("/api/resources?type=Poster").status_code == 400
    assert admin_client.post("/api/admin/resources", json={"key": "x-1", "title": "x", "type": "Link", "language": "xx"}).status_code == 400


def test_replacing_a_file_removes_the_old_one(admin_client, db):
    rid = _new(admin_client)["id"]
    _upload(admin_client, rid, "v1.pdf")
    admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Published"})
    _upload(admin_client, rid, "v2.pdf", PDF + b"% v2\n")
    keys = get_storage().list(f"resources/{rid}")
    assert len(keys) == 1 and keys[0].endswith("/v2.pdf")
    # The published resource's only file cannot be removed while it is published.
    assert admin_client.delete(f"/api/admin/resources/{rid}/file").status_code == 400
    admin_client.patch(f"/api/admin/resources/{rid}", json={"status": "Draft"})
    assert admin_client.delete(f"/api/admin/resources/{rid}/file").json()["has_file"] is False
    assert get_storage().list(f"resources/{rid}") == []


def test_students_cannot_manage_resources(student_client):
    assert student_client.get("/api/admin/resources").status_code == 403
    assert student_client.post("/api/admin/resources", json={"key": "k-1", "title": "t", "type": "Link"}).status_code == 403
