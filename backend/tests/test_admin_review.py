from fastapi.testclient import TestClient
from sqlalchemy import select

from app import jobs
from app.main import app
from app.models import AdminReview, DialogueAttempt, Job, ScoringStatus, SegmentAttempt
from app.services.ai.llm import LLMError, MockProvider
from app.services.stt import MockProvider as MockSTT

from .conftest import login, signup
from .factories import make_dialogue
from .test_scoring_pipeline import answer_audio, record, reset_mocks, segment_ids  # noqa: F401


def scored_attempt(db, answer_audio, transcript="Reference 1.1"):  # noqa: F811
    student = TestClient(app)
    signup(student)
    d = make_dialogue(db, is_free=True, segments=2, mus_per_segment=2)
    aid = student.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    s1, s2 = segment_ids(student, aid)
    record(student, aid, s1, answer_audio)
    MockSTT.override = transcript
    student.post(f"/api/attempts/{aid}/submit")
    jobs.run_until_empty()
    return aid, s1, s2


def test_students_list_and_detail(admin_client, db, answer_audio):  # noqa: F811
    aid, _, _ = scored_attempt(db, answer_audio)
    rows = admin_client.get("/api/admin/students?q=student").json()
    assert rows[0]["email"] == "student@example.com" and rows[0]["dialogue_attempts"] == 1
    assert rows[0]["subscription_status"] == "Inactive" and rows[0]["average_dialogue_score"] == 41.5
    detail = admin_client.get(f"/api/admin/students/{rows[0]['id']}").json()
    assert detail["attempts"][0]["id"] == aid and detail["payments"] == []
    assert admin_client.get("/api/admin/students?status=Active").json() == []


def test_attempt_detail_has_ai_output_and_recording_access(admin_client, db, answer_audio):  # noqa: F811
    aid, s1, _ = scored_attempt(db, answer_audio)
    detail = admin_client.get(f"/api/admin/attempts/{aid}").json()
    seg = detail["dialogues"][0]["segments"][0]
    assert detail["student"]["email"] == "student@example.com" and seg["stt_words"] and "analysis" in seg["timing"]
    runs = admin_client.get(f"/api/admin/segment-attempts/{s1}/runs").json()
    assert {r["kind"] for r in runs} == {"stt", "evaluation"}
    ev = next(r for r in runs if r["kind"] == "evaluation")
    assert ev["request_data"]["system"] and ev["processed_result"]["meaning_units"]
    assert admin_client.get(f"/api/attempts/{aid}/segments/{s1}/recording").status_code == 200


def test_override_recalculates_totals(admin_client, db, answer_audio):  # noqa: F811
    aid, s1, _ = scored_attempt(db, answer_audio)  # 41.5: MU omitted (-1), pause (-0.5), skipped seg (-2)
    seg = admin_client.get(f"/api/admin/attempts/{aid}").json()["dialogues"][0]["segments"][0]
    omitted = next(a for a in seg["accuracy"] if a["result"] == "Omission")
    r = admin_client.post(f"/api/admin/segment-attempts/{s1}/override",
                          json={"target_type": "accuracy", "target_id": omitted["id"], "revised_deduction": 0,
                                "notes": "Conveyed with a synonym; transcription missed it."})
    assert r.status_code == 200 and r.json()["deductions"]["accuracy"] == 0 and r.json()["reviewed"]
    assert next(a for a in r.json()["accuracy"] if a["id"] == omitted["id"])["overridden"]
    db.expire_all()
    da = db.scalar(select(DialogueAttempt))
    assert da.total_score == 42.5
    review = db.scalar(select(AdminReview))
    assert review.original_deduction == 1 and review.revised_deduction == 0 and "synonym" in review.review_notes
    # Student sees the new total
    student = TestClient(app)
    login(student, "student@example.com", "student-pass-1")
    assert student.get(f"/api/attempts/{aid}/results").json()["total_score"] == 42.5
    # A note is required
    bad = admin_client.post(f"/api/admin/segment-attempts/{s1}/override",
                            json={"target_type": "accuracy", "target_id": omitted["id"], "revised_deduction": 1, "notes": ""})
    assert bad.status_code == 422


def test_manual_item_and_pronunciation_review(admin_client, db, answer_audio):  # noqa: F811
    aid, s1, _ = scored_attempt(db, answer_audio)
    r = admin_client.post(f"/api/admin/segment-attempts/{s1}/items",
                          json={"criterion": "language", "type": "Grammar", "student_text": "ay sa",
                                "explanation": "Wrong marker", "notes": "Teacher check"})
    assert r.status_code == 200 and r.json()["deductions"]["language"] == 0.5
    db.expire_all()
    assert db.scalar(select(DialogueAttempt)).total_score == 41
    assert admin_client.post(f"/api/admin/segment-attempts/{s1}/items",
                             json={"criterion": "language", "type": "Nonsense", "explanation": "x x"}).status_code == 400


def test_failed_segment_scored_by_hand_and_rescore(admin_client, db, answer_audio):  # noqa: F811
    def down(*a):
        raise LLMError("bad request", retryable=False)

    MockProvider.responder = down
    aid, s1, _ = scored_attempt(db, answer_audio)
    queue = admin_client.get("/api/admin/review-queue").json()
    assert queue[0]["segment_attempt_id"] == s1 and queue[0]["scoring_status"] == "Failed"
    db.expire_all()
    assert db.scalar(select(DialogueAttempt)).scoring_status == ScoringStatus.FAILED

    # Teacher marks it as omitted by hand, then confirms the segment
    MockProvider.responder = None
    r = admin_client.post(f"/api/admin/segment-attempts/{s1}/items",
                          json={"criterion": "insertion", "student_text": "x", "explanation": "Added detail"})
    assert r.status_code == 200
    admin_client.post(f"/api/admin/segment-attempts/{s1}/reviewed", json={"notes": "Scored by hand"})
    db.expire_all()
    da = db.scalar(select(DialogueAttempt))
    assert da.scoring_status == ScoringStatus.COMPLETED and da.total_score == 42  # -1 insertion, -2 skipped segment
    assert admin_client.get("/api/admin/review-queue").json() == []

    # Re-score replaces the AI results
    assert admin_client.post(f"/api/admin/segment-attempts/{s1}/rescore").json() == {"ok": True}
    assert db.query(Job).filter(Job.status == "queued").count() == 1
    jobs.run_until_empty()
    db.expire_all()
    sa = db.scalar(select(SegmentAttempt).where(SegmentAttempt.id == s1))
    assert sa.scoring_status == ScoringStatus.COMPLETED
