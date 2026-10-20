"""Stripe Checkout, customer portal and webhook handling.

Webhook handlers work on the raw event JSON (dicts), so they are easy to test and do not depend on SDK object
shapes across Stripe API versions. Every event id is stored once (StripeEvent), which makes delivery idempotent.
"""
import json
import logging
import time
import uuid
from datetime import UTC, datetime

import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Payment, Plan, StripeEvent, Subscription, SubscriptionStatus, User
from ..settings import get_settings
from .email import send_template
from .enrolment import access_is_manual

log = logging.getLogger("billing")


class BillingNotConfigured(RuntimeError):
    pass


def client() -> stripe.StripeClient:
    key = get_settings().stripe_secret_key
    if not key:
        raise BillingNotConfigured("Payments are not configured (STRIPE_SECRET_KEY missing)")
    return stripe.StripeClient(key)


# ------------------------------------------------------------------ prices

_price_cache: dict[str, tuple[float, str]] = {}


def format_amount(amount: int | None, currency: str, interval: str | None = None) -> str:
    if amount is None:
        return ""
    value = amount / 100
    text = f"${value:,.0f}" if value == int(value) else f"${value:,.2f}"
    text += f" {currency.upper()}"
    return f"{text} / {interval}" if interval else text


def price_display(plan: Plan) -> str:
    """Admin-set display text wins; otherwise read the Stripe Price (cached 10 minutes); otherwise empty."""
    if plan.price_display:
        return plan.price_display
    if not plan.stripe_price_id or not get_settings().stripe_secret_key:
        return ""
    cached = _price_cache.get(plan.stripe_price_id)
    if cached and cached[0] > time.time():
        return cached[1]
    try:
        p = client().v1.prices.retrieve(plan.stripe_price_id)
        interval = p.recurring.interval if getattr(p, "recurring", None) else None
        text = format_amount(p.unit_amount, p.currency, interval)
    except stripe.StripeError:
        log.exception("could not load Stripe price %s", plan.stripe_price_id)
        text = ""
    _price_cache[plan.stripe_price_id] = (time.time() + 600, text)
    return text


# ------------------------------------------------------------------ checkout / portal

def ensure_customer(db: Session, user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = client().v1.customers.create(params={
        "email": user.email, "name": user.full_name, "metadata": {"user_id": str(user.id)}})
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def create_checkout(db: Session, user: User, plan: Plan) -> str:
    s = get_settings()
    mode = s.stripe_checkout_mode
    params: dict = {
        "mode": mode,
        "customer": ensure_customer(db, user),
        "client_reference_id": str(user.id),
        "line_items": [{"price": plan.stripe_price_id, "quantity": 1}],
        "metadata": {"user_id": str(user.id), "plan_key": plan.key},
        "success_url": f"{s.app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{s.app_url}/pricing?cancelled=1",
        "allow_promotion_codes": False,
    }
    if mode == "subscription":
        params["subscription_data"] = {"metadata": {"user_id": str(user.id), "plan_key": plan.key}}
    else:
        params["invoice_creation"] = {"enabled": True}  # gives a receipt / invoice for one-off payments
    session = client().v1.checkout.sessions.create(params=params)
    return session.url


def create_portal(db: Session, user: User) -> str:
    if not user.stripe_customer_id:
        raise BillingNotConfigured("No billing account yet")
    session = client().v1.billing_portal.sessions.create(params={
        "customer": user.stripe_customer_id, "return_url": f"{get_settings().app_url}/account"})
    return session.url


# ------------------------------------------------------------------ webhook

STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIAL,
    "past_due": SubscriptionStatus.EXPIRED,
    "unpaid": SubscriptionStatus.EXPIRED,
    "canceled": SubscriptionStatus.EXPIRED,
    "incomplete_expired": SubscriptionStatus.EXPIRED,
    "incomplete": SubscriptionStatus.INACTIVE,
    "paused": SubscriptionStatus.INACTIVE,
}


def verify_event(payload: bytes, signature: str) -> dict:
    """Raises ValueError / stripe.SignatureVerificationError when the signature is bad."""
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise BillingNotConfigured("STRIPE_WEBHOOK_SECRET missing")
    stripe.WebhookSignature.verify_header(payload.decode("utf-8"), signature, secret, tolerance=300)
    return json.loads(payload)


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def _user_for(db: Session, obj: dict) -> User | None:
    meta = obj.get("metadata") or {}
    for raw in (meta.get("user_id"), obj.get("client_reference_id")):
        if raw:
            try:
                user = db.get(User, uuid.UUID(raw))
            except ValueError:
                user = None
            if user:
                return user
    customer = obj.get("customer")
    if isinstance(customer, dict):
        customer = customer.get("id")
    if customer:
        return db.scalar(select(User).where(User.stripe_customer_id == customer))
    return None


def _plan_for(db: Session, obj: dict) -> Plan | None:
    key = (obj.get("metadata") or {}).get("plan_key")
    if key:
        return db.scalar(select(Plan).where(Plan.key == key))
    items = ((obj.get("items") or {}).get("data")) or (((obj.get("lines") or {}).get("data")) or [])
    for item in items:
        price = item.get("price") or (item.get("pricing") or {}).get("price_details") or {}
        price_id = price.get("id") if isinstance(price, dict) else price
        if price_id:
            plan = db.scalar(select(Plan).where(Plan.stripe_price_id == price_id))
            if plan:
                return plan
    return None


def _period_end(sub: dict) -> datetime | None:
    # Newer API versions put current_period_end on the subscription items.
    if sub.get("current_period_end"):
        return _ts(sub["current_period_end"])
    items = (sub.get("items") or {}).get("data") or []
    ends = [i.get("current_period_end") for i in items if i.get("current_period_end")]
    return _ts(max(ends)) if ends else None


def _is_stale(row: Subscription | None, created: datetime | None) -> bool:
    """Stripe does not guarantee delivery order: never let an older event overwrite a newer state."""
    return bool(row and created and row.last_event_at and created < row.last_event_at)


def _invoice_subscription_id(invoice: dict) -> str | None:
    sub = invoice.get("subscription") or ((invoice.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    return sub.get("id") if isinstance(sub, dict) else sub


def _apply_subscription(db: Session, sub: dict, created: datetime | None, deleted: bool = False) -> None:
    user = _user_for(db, sub)
    if not user:
        log.warning("subscription %s: no matching user", sub.get("id"))
        return
    row = db.scalar(select(Subscription).where(Subscription.stripe_subscription_id == sub["id"]))
    if _is_stale(row, created):
        log.info("ignoring out-of-order event for %s", sub["id"])
        return
    if not row:
        row = Subscription(user_id=user.id, stripe_subscription_id=sub["id"], status=sub.get("status", ""))
        db.add(row)
    row.last_event_at = created or row.last_event_at
    plan = _plan_for(db, sub)
    if plan:
        row.plan_id = plan.id
    row.status = "canceled" if deleted else sub.get("status", row.status)
    row.current_period_end = _period_end(sub)
    row.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    user.subscription_status = SubscriptionStatus.EXPIRED if deleted else STATUS_MAP.get(
        row.status, SubscriptionStatus.INACTIVE)
    user.access_expires_at = None  # Stripe now manages access (replaces a manual grant's end date)
    customer = sub.get("customer")
    if customer and not user.stripe_customer_id:
        user.stripe_customer_id = customer


def _record_payment(db: Session, user: User, plan: Plan | None, *, invoice_id=None, payment_intent=None,
                    session_id=None, amount=0, currency="aud", receipt_url="") -> Payment | None:
    if invoice_id and db.scalar(select(Payment).where(Payment.stripe_invoice_id == invoice_id)):
        return None  # already recorded
    payment = Payment(user_id=user.id, plan_id=plan.id if plan else None, stripe_invoice_id=invoice_id,
                      stripe_payment_intent_id=payment_intent, stripe_checkout_session_id=session_id,
                      amount=amount or 0, currency=currency or "aud", receipt_url=receipt_url or "")
    db.add(payment)
    return payment


def _send_receipt(db: Session, user: User, plan: Plan | None, payment: Payment) -> None:
    s = get_settings()
    send_template(db, "receipt", user.email, {
        "first_name": user.first_name, "plan_name": plan.name if plan else "CCL practice plan",
        "amount_display": format_amount(payment.amount, payment.currency),
        "date": datetime.now(UTC).strftime("%d %b %Y"), "receipt_url": payment.receipt_url,
        "dashboard_url": f"{s.app_url}/dashboard"}, user_id=user.id)


def _on_checkout_completed(db: Session, session: dict, created: datetime | None = None) -> None:
    user = _user_for(db, session)
    if not user:
        log.warning("checkout %s: no matching user", session.get("id"))
        return
    if session.get("customer") and not user.stripe_customer_id:
        user.stripe_customer_id = session["customer"]
    if session.get("payment_status") not in ("paid", "no_payment_required"):
        return  # async payment methods: wait for checkout.session.async_payment_succeeded
    plan = _plan_for(db, session)
    if session.get("mode") == "payment":
        # One-off purchase: unlock now and record the payment (subscriptions are recorded from invoices).
        user.subscription_status, user.access_expires_at = SubscriptionStatus.ACTIVE, None
        payment = _record_payment(db, user, plan, invoice_id=session.get("invoice"),
                                  payment_intent=session.get("payment_intent"), session_id=session.get("id"),
                                  amount=session.get("amount_total"), currency=session.get("currency"))
        db.flush()
        if payment:
            _send_receipt(db, user, plan, payment)
    else:
        # Unlock immediately; the subscription events then keep the status in sync.
        # (A teacher-granted trial is replaced; a Stripe trial is left for the subscription events to confirm.)
        if user.subscription_status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL) or access_is_manual(db, user):
            user.subscription_status = SubscriptionStatus.ACTIVE
        user.access_expires_at = None
        if session.get("subscription"):
            row = db.scalar(select(Subscription).where(Subscription.stripe_subscription_id == session["subscription"]))
            if not row:
                db.add(Subscription(user_id=user.id, plan_id=plan.id if plan else None, status="active",
                                    stripe_subscription_id=session["subscription"],
                                    stripe_checkout_session_id=session.get("id")))


def _on_invoice_paid(db: Session, invoice: dict, created: datetime | None = None) -> None:
    user = _user_for(db, invoice)
    if not user or not invoice.get("amount_paid"):
        return
    sub_id = _invoice_subscription_id(invoice)
    row = db.scalar(select(Subscription).where(Subscription.stripe_subscription_id == sub_id)) if sub_id else None
    if row and not _is_stale(row, created):
        # A paid renewal (e.g. a successful retry after a failed payment) restores access.
        user.subscription_status, user.access_expires_at = SubscriptionStatus.ACTIVE, None
        row.last_event_at = created or row.last_event_at
    plan = _plan_for(db, invoice)
    payment = _record_payment(db, user, plan, invoice_id=invoice.get("id"),
                              payment_intent=invoice.get("payment_intent"), amount=invoice.get("amount_paid"),
                              currency=invoice.get("currency"), receipt_url=invoice.get("hosted_invoice_url", ""))
    db.flush()
    if payment:
        _send_receipt(db, user, plan, payment)


def _on_invoice_failed(db: Session, invoice: dict, created: datetime | None = None) -> None:
    user = _user_for(db, invoice)
    if not user:
        return
    sub_id = _invoice_subscription_id(invoice)
    row = db.scalar(select(Subscription).where(Subscription.stripe_subscription_id == sub_id)) if sub_id else None
    if _is_stale(row, created):
        return
    user.subscription_status = SubscriptionStatus.EXPIRED
    if row:
        row.last_event_at = created or row.last_event_at


HANDLERS = {
    "checkout.session.completed": _on_checkout_completed,
    "checkout.session.async_payment_succeeded": _on_checkout_completed,
    "customer.subscription.created": lambda db, o, c: _apply_subscription(db, o, c),
    "customer.subscription.updated": lambda db, o, c: _apply_subscription(db, o, c),
    "customer.subscription.deleted": lambda db, o, c: _apply_subscription(db, o, c, deleted=True),
    "invoice.paid": _on_invoice_paid,
    "invoice.payment_succeeded": _on_invoice_paid,
    "invoice.payment_failed": _on_invoice_failed,
}


def handle_event(db: Session, event: dict) -> str:
    """Returns "processed", "duplicate" or "ignored"."""
    try:
        db.add(StripeEvent(event_id=event["id"], event_type=event["type"], payload=event))
        db.flush()
    except IntegrityError:
        db.rollback()
        return "duplicate"
    handler = HANDLERS.get(event["type"])
    if handler:
        handler(db, event["data"]["object"], _ts(event.get("created")))
    db.commit()
    return "processed" if handler else "ignored"
