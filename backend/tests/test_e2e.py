"""End-to-end journey through the real API (providers mocked, Stripe events signed like test mode)."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import jobs
from app.main import app
from app.models import EmailLog, Plan
from app.services.stt import MockProvider as MockSTT

from .conftest import login, signup
from .factories import make_course
from .test_billing import SECRET, event, send, stripe_env  # noqa: F401
from .test_scoring_pipeline import answer_audio, record, reset_mocks  # noqa: F401


def test_full_student_journey(db, stripe_env, answer_audio, monkeypatch):  # noqa: F811
    # --- Admin sets up content: CSV import is covered elsewhere; here the admin builds a mock test via the API.
    from .factories import make_dialogue

    a = make_dialogue(db, key="health-gp", segments=2, mus_per_segment=2)
    b = make_dialogue(db, key="legal-lease", segments=2, mus_per_segment=2, topic="Legal")
    course = make_course(db, key="exam-prep", lessons=2, free_lessons=0)
    admin = TestClient(app)
    login(admin, "admin@example.com", "admin-pass-123")
    mock = admin.post("/api/admin/mock-tests", json={"key": "mock-1", "title": "Mock Test 1", "status": "Published",
                                                      "dialogue_ids": [str(a.id), str(b.id)]}).json()

    # --- Sign up; paid content is locked
    student = TestClient(app)
    me = signup(student, email="maria@example.com")
    assert student.post("/api/attempts", json={"mock_test_id": mock["id"]}).status_code == 402
    lesson_id = student.get(f"/api/courses/{course.id}").json()["lessons"][0]["id"]
    assert student.get(f"/api/lessons/{lesson_id}").status_code == 402

    # --- Pay: checkout session (Stripe stubbed) then the signed webhooks Stripe sends in test mode
    from app.services import billing

    class Obj:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class FakeStripe:
        class v1:
            class customers:
                create = staticmethod(lambda params: Obj(id="cus_maria"))

            class checkout:
                class sessions:
                    create = staticmethod(lambda params: Obj(url="https://checkout.stripe.com/c/pay/cs_test_1"))

    monkeypatch.setattr(billing, "client", lambda: FakeStripe)
    assert student.post("/api/billing/checkout", json={"plan_key": "self-study"}).json()["url"].startswith("https://checkout.stripe.com")
    send(student, event("checkout.session.completed", {
        "id": "cs_test_1", "mode": "subscription", "payment_status": "paid", "client_reference_id": me["id"],
        "customer": "cus_maria", "subscription": "sub_1", "metadata": {"user_id": me["id"], "plan_key": "self-study"}}))
    send(student, event("invoice.paid", {"id": "in_1", "customer": "cus_maria", "amount_paid": 4900, "currency": "aud",
                                         "hosted_invoice_url": "https://invoice.stripe.com/i/test"}))
    assert student.get("/api/me").json()["has_active_plan"] is True

    # --- Course lesson
    assert student.get(f"/api/lessons/{lesson_id}").status_code == 200
    assert student.post(f"/api/lessons/{lesson_id}/complete").json() == {"completed": True}

    # --- Full mock test: info pages, every segment played and answered, submit
    aid = student.post("/api/attempts", json={"mock_test_id": mock["id"]}).json()["id"]
    student.post(f"/api/attempts/{aid}/step", json={"step": "info2"})
    student.post(f"/api/attempts/{aid}/step", json={"step": "segment"})
    state = student.get(f"/api/attempts/{aid}/state").json()
    for d in state["dialogues"]:
        for s in d["segments"]:
            record(student, aid, s["segment_attempt_id"], answer_audio)
    student.post(f"/api/attempts/{aid}/step", json={"step": "summary"})
    MockSTT.override = "Reference 1.1 Reference 1.2 Reference 2.1"  # one MU missing in every second segment
    assert student.post(f"/api/attempts/{aid}/submit").status_code == 200

    # --- Scoring in the worker
    assert jobs.run_until_empty() == 4
    r = student.get(f"/api/attempts/{aid}/results").json()
    assert r["scoring_status"] == "Completed"
    # Per dialogue: seg 1 all MUs found, seg 2 one MU missing (-1); each recording has one long pause (-0.5 x 2)
    assert [d["score"] for d in r["dialogues"]] == [43, 43] and r["total_score"] == 86 and r["result"] == "Pass"

    # --- Admin overrides one deduction; totals follow
    detail = admin.get(f"/api/admin/attempts/{aid}").json()
    seg = detail["dialogues"][0]["segments"][1]
    omission = next(x for x in seg["accuracy"] if x["result"] == "Omission")
    admin.post(f"/api/admin/segment-attempts/{seg['segment_attempt_id']}/override",
               json={"target_type": "accuracy", "target_id": omission["id"], "revised_deduction": 0,
                     "notes": "Teacher accepts the rendering"})
    r = student.get(f"/api/attempts/{aid}/results").json()
    assert r["dialogues"][0]["score"] == 44 and r["total_score"] == 87

    # --- Emails
    templates = [e.template for e in db.scalars(select(EmailLog).where(EmailLog.to == "maria@example.com")
                                                .order_by(EmailLog.created_at))]
    assert templates == ["welcome", "receipt", "results_ready"]
    dash = student.get("/api/dashboard").json()
    assert dash["average_mock_score"] == 87 and dash["recent"][0]["id"] == aid
    assert db.scalar(select(Plan).where(Plan.key == "self-study")).stripe_price_id == "price_selfstudy"
