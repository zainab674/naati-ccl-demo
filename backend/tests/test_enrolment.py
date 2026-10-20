"""Manual enrolment by teachers/admins (MVP_SPEC module 13)."""
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Subscription, SubscriptionStatus, User
from app.services.email import ConsoleProvider

from .conftest import login
from .factories import make_dialogue
from .test_billing import event, send, stripe_env  # noqa: F401

SYDNEY = ZoneInfo("Australia/Sydney")


def _create(admin, **kw):
    body = {"first_name": "Dana", "last_name": "Demo", "email": "dana@example.com", "language": "fil",
            "access": "Trial", **kw}
    return admin.post("/api/admin/students", json=body)


def _user(db, email="dana@example.com") -> User:
    db.expire_all()
    return db.scalar(select(User).where(User.email == email))


def test_create_with_password_gives_access_and_can_sign_in(admin_client, db):
    d = make_dialogue(db, is_free=False)
    r = _create(admin_client, password="demo-pass-1", send_invite=False)
    assert r.status_code == 201, r.text
    u = _user(db)
    assert u.subscription_status == SubscriptionStatus.TRIAL and u.preferred_language.code == "fil"
    assert u.enrolled_by_id is not None and not ConsoleProvider.outbox
    grant = db.scalar(select(Subscription).where(Subscription.user_id == u.id))
    assert grant.source == "manual" and grant.status == "trialing" and grant.granted_by_id is not None

    student = TestClient(app)
    me = login(student, "dana@example.com", "demo-pass-1")
    assert me["has_active_plan"] and me["subscription_status"] == "Trial"
    assert student.post("/api/attempts", json={"dialogue_id": str(d.id)}).status_code == 200  # paid dialogue opens


def test_invite_link_sets_password(admin_client, db):
    assert _create(admin_client, access="Active").status_code == 201
    msg = ConsoleProvider.outbox[-1]
    assert msg.to == "dana@example.com" and "Set your password" in msg.html
    token = re.search(r"token=([\w-]+)", msg.text).group(1)
    student = TestClient(app)
    r = student.post("/api/auth/reset-password", json={"token": token, "password": "chosen-pass-1"})
    assert r.status_code == 200 and r.json()["has_active_plan"]
    # The invite link is single-use.
    assert student.post("/api/auth/reset-password", json={"token": token, "password": "x" * 9}).status_code == 400


def test_create_needs_a_way_to_sign_in_and_rejects_duplicates(admin_client, db):
    assert _create(admin_client, send_invite=False).status_code == 400
    assert _create(admin_client, password="demo-pass-1").status_code == 201
    assert _create(admin_client, password="demo-pass-1", email="DANA@example.com").status_code == 409
    assert _create(admin_client, email="other@example.com", language="xx").status_code == 400


def test_access_end_date_expires_automatically(admin_client, db):
    today = datetime.now(SYDNEY).date()
    _create(admin_client, password="demo-pass-1", send_invite=False, access_until=today.isoformat())
    u = _user(db)
    end = u.access_expires_at.astimezone(SYDNEY)
    assert (end.date(), end.hour, end.minute) == (today, 23, 59)  # all of the last day, Australian time
    student = TestClient(app)
    assert login(student, "dana@example.com", "demo-pass-1")["has_active_plan"]
    u.access_expires_at = datetime.now(UTC) - timedelta(minutes=1)  # the end date has passed
    db.commit()
    me = student.get("/api/me").json()
    assert not me["has_active_plan"] and me["subscription_status"] == "Expired"
    assert [s["email"] for s in admin_client.get("/api/admin/students?status=Expired").json()] == ["dana@example.com"]
    assert admin_client.get("/api/admin/students?status=Trial").json() == []


def test_past_end_date_is_rejected(admin_client):
    assert _create(admin_client, password="demo-pass-1", access_until="2020-01-01").status_code == 400


def test_change_and_revoke_access_keeps_history(admin_client, db):
    _create(admin_client, password="demo-pass-1", send_invite=False)
    uid = _user(db).id
    until = (date.today() + timedelta(days=30)).isoformat()
    r = admin_client.post(f"/api/admin/students/{uid}/access", json={"access": "Active", "access_until": until, "note": "Paid cash"})
    assert r.status_code == 200 and r.json()["stripe_managed"] is False
    assert _user(db).subscription_status == SubscriptionStatus.ACTIVE
    admin_client.post(f"/api/admin/students/{uid}/access", json={"access": "None", "note": "Refunded"})
    u = _user(db)
    assert u.subscription_status == SubscriptionStatus.INACTIVE and u.access_expires_at is None
    detail = admin_client.get(f"/api/admin/students/{uid}").json()
    assert [s["status"] for s in detail["subscriptions"]] == ["revoked", "active", "trialing"]
    assert detail["subscriptions"][1]["note"] == "Paid cash" and detail["subscriptions"][1]["granted_by"]


def test_deactivate_signs_student_out(admin_client, db):
    _create(admin_client, password="demo-pass-1", send_invite=False)
    uid = _user(db).id
    student = TestClient(app)
    login(student, "dana@example.com", "demo-pass-1")
    assert admin_client.patch(f"/api/admin/students/{uid}", json={"is_active": False}).status_code == 200
    assert student.get("/api/me").status_code == 401
    assert student.post("/api/auth/login", json={"email": "dana@example.com", "password": "demo-pass-1"}).status_code == 401
    admin_client.patch(f"/api/admin/students/{uid}", json={"is_active": True, "language": None, "first_name": "Dani"})
    u = _user(db)
    assert u.is_active and u.preferred_language_id is None and u.first_name == "Dani"


def test_admin_sets_password(admin_client, db):
    _create(admin_client)
    uid = _user(db).id
    assert admin_client.post(f"/api/admin/students/{uid}/password", json={"password": "short"}).status_code == 422
    assert admin_client.post(f"/api/admin/students/{uid}/password", json={"password": "new-pass-12"}).status_code == 200
    login(TestClient(app), "dana@example.com", "new-pass-12")


def test_cannot_manage_admin_accounts(admin_client, db):
    admin = _user(db, "admin@example.com")
    assert admin_client.patch(f"/api/admin/students/{admin.id}", json={"is_active": False}).status_code == 404
    assert admin_client.post(f"/api/admin/students/{admin.id}/password", json={"password": "x" * 10}).status_code == 404


def test_student_cannot_enrol(student_client):
    assert student_client.post("/api/admin/students", json={"first_name": "x", "email": "x@example.com"}).status_code == 403


CSV = (b"first_name,last_name,email,language,access,access_until,note\n"
       b"Ana,One,ana@example.com,fil,Trial,,demo\n"
       b"Ben,Two,ben@example.com,,Active,31/12/2099,\n"
       b"Cy,Three,student@example.com,fil,Trial,,\n")


def test_bulk_dry_run_then_commit(admin_client, db):
    from .conftest import signup
    signup(TestClient(app))  # student@example.com exists: skipped
    files = {"file": ("students.csv", CSV, "text/csv")}
    dry = admin_client.post("/api/admin/students-import", files=files, data={"commit": "false"}).json()
    assert dry["report"]["ok"] and dry["report"]["summary"] == {"rows": 3, "to_create": 2, "skipped_existing": 1}
    assert not _user(db, "ana@example.com")
    ConsoleProvider.outbox.clear()
    done = admin_client.post("/api/admin/students-import", files=files, data={"commit": "true"}).json()
    assert [c["email"] for c in done["created"]] == ["ana@example.com", "ben@example.com"]
    assert {m.to for m in ConsoleProvider.outbox} == {"ana@example.com", "ben@example.com"}
    ben = _user(db, "ben@example.com")
    assert ben.subscription_status == SubscriptionStatus.ACTIVE and ben.access_expires_at.astimezone(SYDNEY).date() == date(2099, 12, 31)
    # Re-running the same file creates nothing new.
    again = admin_client.post("/api/admin/students-import", files=files, data={"commit": "true"}).json()
    assert again["created"] == [] and again["report"]["summary"]["skipped_existing"] == 3


def test_bulk_reports_errors_and_refuses_commit(admin_client, db):
    bad = (b"first_name,email,language,access,access_until\n"
           b",a@example.com,fil,Trial,\n"
           b"B,not-an-email,fil,Trial,\n"
           b"C,c@example.com,zz,Gold,2020-01-01\n"
           b"D,d@example.com,fil,Trial,\n"
           b"E,D@example.com,fil,Trial,\n")
    files = {"file": ("s.csv", bad, "text/csv")}
    rep = admin_client.post("/api/admin/students-import", files=files).json()["report"]
    cols = sorted((e["row"], e["column"]) for e in rep["errors"])
    assert cols == [(2, "first_name"), (3, "email"), (4, "access"), (4, "access_until"), (4, "language"), (6, "email")]
    assert admin_client.post("/api/admin/students-import", files=files, data={"commit": "true"}).status_code == 400
    assert not _user(db, "d@example.com")


def test_trial_student_can_buy_and_stripe_takes_over(admin_client, db, stripe_env, monkeypatch):  # noqa: F811
    from app.services import billing

    _create(admin_client, password="demo-pass-1", send_invite=False,
            access_until=(date.today() + timedelta(days=7)).isoformat())
    student = TestClient(app)
    login(student, "dana@example.com", "demo-pass-1")
    monkeypatch.setattr(billing, "create_checkout", lambda db, u, p: "https://checkout.stripe.com/x")
    assert student.post("/api/billing/checkout", json={"plan_key": "self-study"}).status_code == 200
    u = _user(db)
    send(student, event("checkout.session.completed", {
        "id": "cs_1", "mode": "subscription", "payment_status": "paid", "customer": "cus_1", "subscription": "sub_1",
        "client_reference_id": str(u.id), "metadata": {"user_id": str(u.id), "plan_key": "self-study"}}))
    u = _user(db)
    assert u.subscription_status == SubscriptionStatus.ACTIVE and u.access_expires_at is None  # no manual end date
    # Now paying through Stripe: a second checkout is refused.
    assert student.post("/api/billing/checkout", json={"plan_key": "self-study"}).status_code == 409
