from .conftest import signup


def test_admin_guard(client):
    assert client.get("/api/admin/overview").status_code == 401
    signup(client)
    assert client.get("/api/admin/overview").status_code == 403


def test_admin_overview(admin_client):
    r = admin_client.get("/api/admin/overview")
    assert r.status_code == 200
    assert r.json()["students"] == 0
