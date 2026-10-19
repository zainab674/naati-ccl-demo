import hashlib
import hmac
import json
import time
import uuid

import pytest
from sqlalchemy import select

from app.models import EmailLog, Payment, Plan, StripeEvent, Subscription, SubscriptionStatus, User
from app.settings import get_settings

from .conftest import signup

SECRET = "whsec_test_secret"


@pytest.fixture
def stripe_env(db):
    s = get_settings()
    old = (s.stripe_webhook_secret, s.stripe_secret_key)
    s.stripe_webhook_secret = SECRET
    plan = db.scalar(select(Plan).where(Plan.key == "self-study"))
    plan.stripe_price_id, plan.price_display = "price_selfstudy", "$99 AUD / month"
    db.commit()
    yield
    s.stripe_webhook_secret, s.stripe_secret_key = old


def send(client, event: dict, secret=SECRET):
    payload = json.dumps(event)
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/stripe/webhook", content=payload,
                       headers={"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"})


def event(type_, obj):
    return {"id": f"evt_{uuid.uuid4().hex}", "type": type_, "data": {"object": obj}}


def user(db, email="student@example.com"):
    db.expire_all()
    return db.scalar(select(User).where(User.email == email))


def test_bad_signature_rejected(client, stripe_env):
    r = send(client, event("invoice.paid", {}), secret="whsec_wrong")
    assert r.status_code == 400


def test_subscription_lifecycle(client, db, stripe_env):
    u = signup(client)
    uid = u["id"]
    checkout = event("checkout.session.completed", {
        "id": "cs_1", "mode": "subscription", "payment_status": "paid", "client_reference_id": uid,
        "customer": "cus_1", "subscription": "sub_1", "metadata": {"user_id": uid, "plan_key": "self-study"}})
    assert send(client, checkout).json()["result"] == "processed"
    assert user(db).subscription_status == SubscriptionStatus.ACTIVE
    assert user(db).stripe_customer_id == "cus_1"
    # Unlock is visible to the student immediately
    assert client.get("/api/me").json()["has_active_plan"] is True

    # Same event delivered twice: idempotent
    assert send(client, checkout).json()["result"] == "duplicate"
    assert db.query(StripeEvent).count() == 1

    end = int(time.time()) + 30 * 86400
    sub = {"id": "sub_1", "customer": "cus_1", "status": "active", "cancel_at_period_end": False,
           "metadata": {"user_id": uid, "plan_key": "self-study"},
           "items": {"data": [{"current_period_end": end, "price": {"id": "price_selfstudy"}}]}}
    send(client, event("customer.subscription.updated", sub))
    row = db.scalar(select(Subscription).where(Subscription.stripe_subscription_id == "sub_1"))
    assert row.status == "active" and int(row.current_period_end.timestamp()) == end
    assert row.plan.key == "self-study"

    send(client, event("invoice.paid", {"id": "in_1", "customer": "cus_1", "amount_paid": 9900, "currency": "aud",
                                        "hosted_invoice_url": "https://invoice.stripe.com/i/x"}))
    pay = db.scalar(select(Payment).where(Payment.stripe_invoice_id == "in_1"))
    assert pay.amount == 9900 and pay.receipt_url.startswith("https://")
    assert db.scalar(select(EmailLog).where(EmailLog.template == "receipt")) is not None

    send(client, event("invoice.payment_failed", {"id": "in_2", "customer": "cus_1"}))
    assert user(db).subscription_status == SubscriptionStatus.EXPIRED

    send(client, event("customer.subscription.updated", {**sub, "status": "trialing"}))
    assert user(db).subscription_status == SubscriptionStatus.TRIAL

    send(client, event("customer.subscription.deleted", {**sub, "status": "canceled"}))
    assert user(db).subscription_status == SubscriptionStatus.EXPIRED
    assert client.get("/api/me").json()["has_active_plan"] is False


def test_one_off_payment_mode(client, db, stripe_env):
    uid = signup(client)["id"]
    send(client, event("checkout.session.completed", {
        "id": "cs_2", "mode": "payment", "payment_status": "paid", "client_reference_id": uid, "customer": "cus_2",
        "amount_total": 19900, "currency": "aud", "payment_intent": "pi_1",
        "metadata": {"user_id": uid, "plan_key": "self-study"}}))
    assert user(db).subscription_status == SubscriptionStatus.ACTIVE
    assert db.scalar(select(Payment).where(Payment.stripe_payment_intent_id == "pi_1")).amount == 19900


def test_unpaid_checkout_does_not_unlock(client, db, stripe_env):
    uid = signup(client)["id"]
    send(client, event("checkout.session.completed", {
        "id": "cs_3", "mode": "subscription", "payment_status": "unpaid", "client_reference_id": uid}))
    assert user(db).subscription_status == SubscriptionStatus.INACTIVE


def test_public_plans_and_checkout_guard(client, db, stripe_env):
    plans = client.get("/api/public/plans").json()
    by_key = {p["key"]: p for p in plans}
    assert by_key["self-study"]["price_display"] == "$99 AUD / month"
    assert by_key["coaching"]["contact_only"] is True
    signup(client)
    assert client.post("/api/billing/checkout", json={"plan_key": "coaching"}).status_code == 400
    # No STRIPE_SECRET_KEY in tests: clear 503 rather than a crash
    assert client.post("/api/billing/checkout", json={"plan_key": "self-study"}).status_code == 503


def test_checkout_creates_session(client, db, stripe_env, monkeypatch):
    from app.services import billing

    calls = {}

    class FakeObj:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Fake:
        class v1:
            class customers:
                @staticmethod
                def create(params):
                    calls["customer"] = params
                    return FakeObj(id="cus_new")

            class checkout:
                class sessions:
                    @staticmethod
                    def create(params):
                        calls["session"] = params
                        return FakeObj(url="https://checkout.stripe.com/c/pay/cs_test")

    monkeypatch.setattr(billing, "client", lambda: Fake)
    signup(client)
    r = client.post("/api/billing/checkout", json={"plan_key": "self-study"})
    assert r.json()["url"].startswith("https://checkout.stripe.com/")
    assert calls["session"]["line_items"][0]["price"] == "price_selfstudy"
    assert calls["session"]["metadata"]["plan_key"] == "self-study"
    assert user(db).stripe_customer_id == "cus_new"
