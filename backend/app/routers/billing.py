import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..models import Payment, Plan, Subscription, SubscriptionStatus
from ..services import billing

router = APIRouter(prefix="/api", tags=["billing"])
log = logging.getLogger("billing")


def plan_dict(p: Plan) -> dict:
    return {"key": p.key, "name": p.name, "description": p.description, "features": p.features,
            "price_display": billing.price_display(p), "contact_only": p.contact_only or not p.stripe_price_id}


@router.get("/public/plans")
def list_plans(db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).where(Plan.active).order_by(Plan.sort_order)).all()
    return [plan_dict(p) for p in plans]


class CheckoutIn(BaseModel):
    plan_key: str


@router.post("/billing/checkout")
def checkout(body: CheckoutIn, cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.scalar(select(Plan).where(Plan.key == body.plan_key, Plan.active))
    if not plan:
        raise HTTPException(404, "Plan not found")
    if plan.contact_only or not plan.stripe_price_id:
        raise HTTPException(400, "This plan is not available for online purchase. Please contact us.")
    if cu.user.subscription_status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
        # Prevents a second, parallel subscription (double billing). Plan changes go through the billing portal.
        raise HTTPException(409, "You already have an active plan. Manage it from your account page.")
    try:
        return {"url": billing.create_checkout(db, cu.user, plan)}
    except billing.BillingNotConfigured as e:
        raise HTTPException(503, str(e)) from e
    except stripe.StripeError as e:
        log.exception("checkout failed")
        raise HTTPException(502, "Payment provider error. Please try again.") from e


@router.post("/billing/portal")
def portal(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return {"url": billing.create_portal(db, cu.user)}
    except billing.BillingNotConfigured as e:
        raise HTTPException(400, str(e)) from e
    except stripe.StripeError as e:
        log.exception("portal failed")
        raise HTTPException(502, "Payment provider error. Please try again.") from e


@router.get("/billing/status")
def billing_status(cu: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.user_id == cu.id)
                    .order_by(Subscription.created_at.desc()))
    payments = db.scalars(select(Payment).where(Payment.user_id == cu.id).order_by(Payment.created_at.desc())).all()
    return {
        "subscription_status": cu.user.subscription_status.value,
        "has_billing_account": bool(cu.user.stripe_customer_id),
        "subscription": None if not sub else {
            "plan": sub.plan.name if sub.plan else None, "status": sub.status,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancel_at_period_end": sub.cancel_at_period_end},
        "payments": [{"amount": p.amount, "currency": p.currency, "receipt_url": p.receipt_url,
                      "created_at": p.created_at.isoformat()} for p in payments],
    }


@router.post("/stripe/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    try:
        event = billing.verify_event(payload, request.headers.get("stripe-signature", ""))
    except billing.BillingNotConfigured as e:
        raise HTTPException(503, str(e)) from e
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise HTTPException(400, "Invalid signature") from e
    result = billing.handle_event(db, event)
    return {"received": True, "result": result}
