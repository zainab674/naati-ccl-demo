"""Dashboard: average of the last 3 attempts and the announcements carousel (MVP scope, module 4)."""
from datetime import timedelta

from app.db import utcnow
from app.models import DialogueAttempt

from .conftest import login, signup
from .factories import make_dialogue

NOW = utcnow()


def _post(admin, **kw):
    body = {"title": "Group session: sight translation", "kind": "live_session", "status": "Published", **kw}
    r = admin.post("/api/admin/announcements", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_dashboard_average_uses_the_last_3_scored_attempts(client, db):
    d = make_dialogue(db, key="free-1", is_free=True)
    me = signup(client)
    for i, score in enumerate([10, 20, 30, 40, 50, 90]):  # 90 is the oldest
        db.add(DialogueAttempt(user_id=me["id"], dialogue_id=d.id, language_pair_id=d.language_pair_id,
                               started_at=NOW - timedelta(days=10 - i if score != 90 else 30), total_score=score))
    db.commit()
    dash = client.get("/api/dashboard").json()
    assert dash["average_dialogue_score"] == 40 and dash["dialogue_scores_counted"] == 3 and dash["average_over"] == 3


def test_carousel_shows_published_current_announcements_for_the_students_language(client, db):
    login(client, "admin@example.com", "admin-pass-123")
    _post(client, title="Everyone", sort_order=1)
    _post(client, title="Filipino class", kind="class", language="fil", event_at=(NOW + timedelta(days=2)).isoformat(),
          link_url="https://zoom.us/j/123", link_label="Join")
    _post(client, title="Hindi only", language="hi")
    _post(client, title="Draft", status="Draft")
    _post(client, title="Expired", ends_at=(NOW - timedelta(days=1)).isoformat())
    _post(client, title="Later", starts_at=(NOW + timedelta(days=3)).isoformat())
    assert client.post("/api/admin/announcements", json={"title": "x", "link_url": "javascript:alert(1)"}).status_code == 400
    assert client.post("/api/admin/announcements", json={"title": "x", "kind": "party"}).status_code == 400
    assert len(client.get("/api/admin/announcements").json()) == 6
    client.post("/api/auth/logout")
    signup(client, language="fil")
    shown = client.get("/api/dashboard").json()["announcements"]
    assert [a["title"] for a in shown] == ["Filipino class", "Everyone"]
    assert shown[0]["kind_label"] == "1-on-1 class" and shown[0]["language_name"] == "Filipino"


def test_announcements_admin_only(client, db):
    signup(client)
    assert client.get("/api/admin/announcements").status_code == 403
