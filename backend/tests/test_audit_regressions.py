"""Regression tests for defects found in the adversarial audit (docs/AUDIT.md). Each was written failing first."""
import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import jobs
from app.main import app
from app.models import (AccuracyCompletenessEvaluation, DialogueAttempt, EmailLog, LanguageQualityError, MeaningUnit,
                        SegmentAttempt, SubscriptionStatus, User)
from app.services.ai.llm import LLMError, MockProvider
from app.services.stt import MockProvider as MockSTT

from .conftest import signup
from .factories import make_dialogue
from .test_billing import event, send, stripe_env  # noqa: F401
from .test_player import activate
from .test_scoring_pipeline import answer_audio, record, reset_mocks, segment_ids  # noqa: F401


def _scored_practice(db, audio, transcript="Reference 1.1", record_both=False):
    student = TestClient(app)
    signup(student)
    d = make_dialogue(db, is_free=True, segments=2, mus_per_segment=2)
    aid = student.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    s1, s2 = segment_ids(student, aid)
    record(student, aid, s1, audio)
    if record_both:
        record(student, aid, s2, audio)
    MockSTT.override = transcript
    student.post(f"/api/attempts/{aid}/submit")
    jobs.run_until_empty()
    return student, aid, s1, s2


# --- A1: a failed segment must not produce a final-looking (inflated) score -----------------------------------------

def test_failed_segment_does_not_publish_inflated_score(db, answer_audio):  # noqa: F811
    def down(*a):
        raise LLMError("bad request", retryable=False)

    MockProvider.responder = down
    student, aid, s1, _ = _scored_practice(db, answer_audio)
    r = student.get(f"/api/attempts/{aid}/results").json()
    assert r["scoring_status"] == "Failed"
    # Before the fix: total_score 43 ("Pass") with the failed segment silently counted as perfect.
    assert r["total_score"] is None and r["result"] is None
    assert student.get("/api/dashboard").json()["average_dialogue_score"] is None


# --- A2: re-scoring must not silently discard a teacher's work, nor re-send the results email -----------------------

def test_rescore_keeps_teacher_items_and_requeues_review(admin_client, db, answer_audio):  # noqa: F811
    _, aid, s1, _ = _scored_practice(db, answer_audio)
    admin_client.post(f"/api/admin/segment-attempts/{s1}/items",
                      json={"criterion": "language", "type": "Grammar", "student_text": "x", "explanation": "Teacher found it"})
    admin_client.post(f"/api/admin/segment-attempts/{s1}/rescore")
    jobs.run_until_empty()
    db.expire_all()
    manual = db.scalars(select(LanguageQualityError).where(LanguageQualityError.segment_attempt_id == s1)).all()
    assert [m.explanation for m in manual] == ["Teacher found it"]
    sa = db.get(SegmentAttempt, s1)
    assert sa.language_quality_deduction == 0.5
    assert db.query(EmailLog).filter(EmailLog.template == "results_ready").count() == 1


# --- A3: editing a Meaning Unit's weight later must not change scores already given --------------------------------

def test_weight_change_after_scoring_does_not_rescore_old_attempts(admin_client, db, answer_audio):  # noqa: F811
    _, aid, s1, s2 = _scored_practice(db, answer_audio)
    db.expire_all()
    before = db.scalar(select(DialogueAttempt)).total_score
    mu2 = db.scalar(select(MeaningUnit).join(AccuracyCompletenessEvaluation,
                                             AccuracyCompletenessEvaluation.meaning_unit_id == MeaningUnit.id)
                    .where(AccuracyCompletenessEvaluation.segment_attempt_id == s1,
                           AccuracyCompletenessEvaluation.result == "Omission"))
    seg = mu2.segment
    body = [{"id": str(m.id), "meaning_unit_number": m.meaning_unit_number, "meaning": m.meaning,
             "weight": 3 if m.id == mu2.id else 1} for m in seg.meaning_units]
    admin_client.put(f"/api/admin/segments/{seg.id}/meaning-units", json=body)
    # Any later recalculation of the old attempt (here: an unrelated override) must keep the original weight.
    other = db.scalar(select(AccuracyCompletenessEvaluation).where(AccuracyCompletenessEvaluation.segment_attempt_id == s1,
                                                                   AccuracyCompletenessEvaluation.result == "Correct"))
    admin_client.post(f"/api/admin/segment-attempts/{s1}/override",
                      json={"target_type": "accuracy", "target_id": str(other.id), "revised_deduction": 0, "notes": "unchanged"})
    db.expire_all()
    assert db.scalar(select(DialogueAttempt)).total_score == before


# --- A4: Stripe events delivered out of order must not cut off a paying student -------------------------------------

def test_out_of_order_subscription_events_keep_access(client, db, stripe_env):  # noqa: F811
    uid = signup(client)["id"]
    now = int(time.time())
    sub = {"id": "sub_9", "customer": "cus_9", "metadata": {"user_id": uid, "plan_key": "self-study"},
           "items": {"data": [{"current_period_end": now + 86400}]}}
    newer = {**event("customer.subscription.updated", {**sub, "status": "active"}), "created": now}
    older = {**event("customer.subscription.updated", {**sub, "status": "past_due"}), "created": now - 600}
    send(client, newer)
    send(client, older)  # Stripe does not guarantee delivery order
    db.expire_all()
    assert db.scalar(select(User).where(User.id == uid)).subscription_status == SubscriptionStatus.ACTIVE
    stale_fail = {**event("invoice.payment_failed", {"id": "in_old", "customer": "cus_9", "subscription": "sub_9"}),
                  "created": now - 300}
    send(client, stale_fail)
    db.expire_all()
    assert db.scalar(select(User).where(User.id == uid)).subscription_status == SubscriptionStatus.ACTIVE


# --- A5: an active subscriber must not be able to open a second subscription ---------------------------------------

def test_active_subscriber_cannot_buy_again(client, db, stripe_env, monkeypatch):  # noqa: F811
    from app.services import billing

    calls = []
    monkeypatch.setattr(billing, "create_checkout", lambda db, u, p: calls.append(1) or "https://checkout.stripe.com/x")
    signup(client)
    activate(db)
    r = client.post("/api/billing/checkout", json={"plan_key": "self-study"})
    assert r.status_code == 409 and calls == []


# --- A6: a late upload from a discarded recording must not overwrite the new recording ------------------------------

def test_discarded_recording_parts_cannot_leak_into_new_recording(db):
    student = TestClient(app)
    signup(student)
    d = make_dialogue(db, is_free=True, segments=1)
    aid = student.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    (sid,) = segment_ids(student, aid)
    student.post(f"/api/attempts/{aid}/segments/{sid}/play")
    base = f"/api/attempts/{aid}/segments/{sid}/recording"
    assert student.put(f"{base}/parts/0?recording=new", content=b"NEW-ANSWER").status_code == 200
    # A retry of part 0 from the recording the student threw away (pressed Repeat) arrives late:
    assert student.put(f"{base}/parts/0?recording=old", content=b"OLD-ANSWER").status_code == 200
    r = student.post(f"{base}/complete", json={"parts": 1, "mime": "audio/webm", "recording": "new"})
    assert r.status_code == 200, r.text
    assert student.get(base).content == b"NEW-ANSWER"
