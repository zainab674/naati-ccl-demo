"""Per-language score gate: until a language is validated against examiners, students see practice feedback (errors,
explanations, suggested versions) but no estimated score, deductions or Pass/Fail anywhere. Staff see everything."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.email import ConsoleProvider
from app.services.scoring.engine import Totals, dialogue_score
from app.settings import scoring_config

from .conftest import login
from .test_admin_review import scored_attempt
from .test_scoring_pipeline import answer_audio, reset_mocks  # noqa: F401


@pytest.mark.score_gate
def test_unvalidated_language_hides_every_score_from_students(client, db, answer_audio):  # noqa: F811
    ConsoleProvider.outbox.clear()
    aid, _, _ = scored_attempt(db, answer_audio)
    student = TestClient(app)
    login(student, "student@example.com", "student-pass-1")
    res = student.get(f"/api/attempts/{aid}/results").json()
    assert res["score_validated"] is False and "not validated" in res["score_notice"]
    assert res["total_score"] is None and res["result"] is None and res["reasons"] == []
    assert set(res["deductions"].values()) == {None}
    seg = res["dialogues"][0]["segments"][0]
    assert res["dialogues"][0]["score"] is None and set(seg["deductions"].values()) == {None}
    assert seg["accuracy"] and all(i["deduction"] is None for i in seg["accuracy"])
    assert seg["accuracy"][0]["explanation"] is not None  # the feedback itself is still there
    assert all(h["total_score"] is None for h in res["history"])
    dash = student.get("/api/dashboard").json()
    assert dash["average_dialogue_score"] is None and dash["recent"][0]["total_score"] is None
    assert student.get("/api/attempts").json()[0]["score_validated"] is False
    assert all(d["best_score"] is None for d in student.get("/api/dialogues").json())
    mail = next(m for m in ConsoleProvider.outbox if "results are ready" in m.subject)
    assert "Estimated score" not in mail.text

    login(client, "admin@example.com", "admin-pass-123")
    staff = client.get(f"/api/attempts/{aid}/results").json()
    assert staff["total_score"] == 41.5 and staff["score_validated"] is False
    me = client.get("/api/admin/students").json()[0]["id"]
    staff_detail = client.get(f"/api/admin/students/{me}").json()
    assert staff_detail["attempts"][0]["total_score"] == 41.5


@pytest.mark.score_gate
def test_validated_language_shows_scores(client, db, answer_audio, monkeypatch):  # noqa: F811
    from app.services import score_visibility
    monkeypatch.setattr(score_visibility, "validated_languages", lambda: frozenset({"fil"}))
    aid, _, _ = scored_attempt(db, answer_audio)
    student = TestClient(app)
    login(student, "student@example.com", "student-pass-1")
    res = student.get(f"/api/attempts/{aid}/results").json()
    assert res["score_validated"] is True and res["total_score"] == 41.5 and res["result"] == "Pass"


def test_meaning_unit_normalisation_is_off_by_default_and_scales_accuracy_when_on():
    cfg = scoring_config()
    assert cfg["accuracy_normalisation"]["enabled"] is False
    assert dialogue_score([Totals(8, 1, 0)], 45, 29, cfg, meaning_units=80).score == 36
    on = {**cfg, "accuracy_normalisation": {"enabled": True, "reference_meaning_units": 40}}
    assert dialogue_score([Totals(8, 1, 0)], 45, 29, on, meaning_units=80).score == 40  # 8 x 40/80 = 4
    assert dialogue_score([Totals(8, 1, 0)], 45, 29, on, meaning_units=20).score == 28  # 8 x 40/20 = 16
    assert dialogue_score([Totals(8, 1, 0)], 45, 29, on).score == 36                     # unknown MU count: unchanged
