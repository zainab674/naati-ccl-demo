import pytest
from sqlalchemy import select

from app import jobs
from app.models import (AIScoringRun, AttemptResult, DialogueAttempt, EmailLog, FluencyError, MockTestAttempt,
                        ScoringStatus, SegmentAttempt)
from app.services.ai.llm import LLMError, MockProvider
from app.services.media_pipeline import run_ffmpeg
from app.services.stt import MockProvider as MockSTT

from .factories import make_dialogue, make_mock
from .test_player import activate


@pytest.fixture(autouse=True)
def reset_mocks():
    yield
    MockSTT.override = None
    MockProvider.responder = None


@pytest.fixture(scope="module")
def answer_audio(tmp_path_factory):
    """1 s silence, 1.5 s 'speech', 3.5 s silence, 1 s 'speech' -> one long pause, no start delay."""
    path = tmp_path_factory.mktemp("rec") / "answer.webm"
    parts = [("anullsrc=r=48000:cl=mono:d=1"), ("sine=frequency=300:duration=1.5"),
             ("anullsrc=r=48000:cl=mono:d=3.5"), ("sine=frequency=300:duration=1")]
    args = []
    for p in parts:
        args += ["-f", "lavfi", "-i", p]
    filt = "".join(f"[{i}]aresample=48000,aformat=channel_layouts=mono[a{i}];" for i in range(4))
    filt += "".join(f"[a{i}]" for i in range(4)) + "concat=n=4:v=0:a=1[out]"
    run_ffmpeg([*args, "-filter_complex", filt, "-map", "[out]", "-c:a", "libopus", str(path)])
    return path.read_bytes()


def record(client, aid, sid, audio):
    client.post(f"/api/attempts/{aid}/segments/{sid}/play")
    r = client.post(f"/api/attempts/{aid}/segments/{sid}/recording",
                    files={"audio": ("a.webm", audio, "audio/webm")},
                    data={"timing": '{"chime_end_ms": 1000, "record_start_ms": 1050}'})
    assert r.status_code == 200, r.text


def segment_ids(client, aid):
    st = client.get(f"/api/attempts/{aid}/state").json()
    return [s["segment_attempt_id"] for d in st["dialogues"] for s in d["segments"]]


def test_practice_attempt_scored_end_to_end(student_client, db, answer_audio):
    d = make_dialogue(db, is_free=True, segments=2, mus_per_segment=2)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    s1, s2 = segment_ids(student_client, aid)
    record(student_client, aid, s1, answer_audio)
    MockSTT.override = "Reference 1.1 lang po"  # MU 1 conveyed, MU 2 omitted
    student_client.post(f"/api/attempts/{aid}/submit")      # segment 2 is skipped
    assert jobs.run_until_empty() == 2

    db.expire_all()
    da = db.scalar(select(DialogueAttempt))
    seg1, seg2 = da.segment_attempts
    assert seg1.scoring_status == ScoringStatus.COMPLETED and seg1.transcript_user == "Reference 1.1 lang po"
    # Segment 1: one omitted MU (-1) + one pause of ~3.5 s measured from the audio (-0.5)
    assert seg1.accuracy_completeness_deduction == 1 and seg1.fluency_deduction == 0.5
    pause = db.scalar(select(FluencyError).where(FluencyError.segment_attempt_id == seg1.id))
    assert pause.error_type.value == "Pause" and pause.detection_method.value == "AudioAnalysis"
    assert 3.0 < pause.duration_seconds < 4.0 and pause.deduction == 0.5
    # Segment 2 skipped: both MUs omitted
    assert seg2.skipped and seg2.accuracy_completeness_deduction == 2
    assert da.scoring_status == ScoringStatus.COMPLETED and da.total_deductions == 3.5 and da.total_score == 41.5
    assert da.result == AttemptResult.PASS and da.finished_at
    runs = {r.kind for r in db.scalars(select(AIScoringRun))}
    assert runs == {"stt", "evaluation"}
    ev_run = db.scalar(select(AIScoringRun).where(AIScoringRun.kind == "evaluation"))
    assert ev_run.prompt_version == "evaluate_segment_v1" and ev_run.processed_result["meaning_units"]
    assert db.scalar(select(EmailLog).where(EmailLog.template == "results_ready")) is not None


def test_mock_test_totals_and_pass_rules(student_client, db, answer_audio):
    activate(db)
    a, b = make_dialogue(db, key="a", segments=1), make_dialogue(db, key="b", segments=1)
    m = make_mock(db, [a, b])
    aid = student_client.post("/api/attempts", json={"mock_test_id": str(m.id)}).json()["id"]
    s1, s2 = segment_ids(student_client, aid)
    record(student_client, aid, s1, answer_audio)
    record(student_client, aid, s2, answer_audio)
    MockSTT.override = "Reference 1.1 Reference 1.2"
    student_client.post(f"/api/attempts/{aid}/submit")
    jobs.run_until_empty()
    db.expire_all()
    ma = db.scalar(select(MockTestAttempt))
    assert ma.scoring_status == ScoringStatus.COMPLETED
    # Each dialogue: only the pause (-0.5) -> 44.5 + 44.5
    assert ma.total_score == 89 and ma.maximum_score == 90 and ma.result == AttemptResult.PASS
    assert db.query(EmailLog).filter(EmailLog.template == "results_ready").count() == 1


def test_silent_recording_counts_as_unanswered_and_needs_review(student_client, db):
    d = make_dialogue(db, is_free=True, segments=1)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    (sid,) = segment_ids(student_client, aid)
    silent = db  # noqa: F841
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.webm"
        run_ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=2", "-c:a", "libopus", str(p)])
        record(student_client, aid, sid, p.read_bytes())
    MockSTT.override = ""
    student_client.post(f"/api/attempts/{aid}/submit")
    jobs.run_until_empty()
    db.expire_all()
    sa = db.scalar(select(SegmentAttempt))
    assert sa.accuracy_completeness_deduction == 2 and sa.needs_review and "No speech" in sa.ai_feedback


def test_evaluator_outage_retries_then_fails_visibly(student_client, db, answer_audio):
    d = make_dialogue(db, is_free=True, segments=1)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    (sid,) = segment_ids(student_client, aid)
    record(student_client, aid, sid, answer_audio)
    MockSTT.override = "Reference 1.1"

    def down(*a):
        raise LLMError("Gemini error 503: unavailable")

    MockProvider.responder = down
    student_client.post(f"/api/attempts/{aid}/submit")
    jobs.run_until_empty(include_delayed=True)
    db.expire_all()
    sa = db.scalar(select(SegmentAttempt))
    assert sa.scoring_status == ScoringStatus.FAILED and sa.needs_review and "503" in sa.scoring_error
    assert db.query(AIScoringRun).filter(AIScoringRun.kind == "evaluation", AIScoringRun.status == "Failed").count() == 4
    da = db.scalar(select(DialogueAttempt))
    assert da.scoring_status == ScoringStatus.FAILED
    assert db.query(EmailLog).filter(EmailLog.template == "results_ready").count() == 0


def test_low_confidence_flags_review(student_client, db, answer_audio):
    d = make_dialogue(db, is_free=True, segments=1)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    (sid,) = segment_ids(student_client, aid)
    record(student_client, aid, sid, answer_audio)
    MockSTT.override = "Reference 1.1 Reference 1.2"
    from app.services.scoring.evaluator import mock_evaluation

    def unsure(system, user, schema):
        data = mock_evaluation({"user": user})
        data["confidence"] = 0.3
        return data

    MockProvider.responder = unsure
    student_client.post(f"/api/attempts/{aid}/submit")
    jobs.run_until_empty()
    db.expire_all()
    sa = db.scalar(select(SegmentAttempt))
    assert sa.scoring_status == ScoringStatus.COMPLETED and sa.needs_review and "low AI confidence" in sa.scoring_error


def test_results_payload(student_client, db, answer_audio):
    d = make_dialogue(db, is_free=True, segments=2, mus_per_segment=2)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    s1, _ = segment_ids(student_client, aid)
    assert student_client.get(f"/api/attempts/{aid}/results").status_code == 409
    record(student_client, aid, s1, answer_audio)
    MockSTT.override = "Reference 1.1"
    student_client.post(f"/api/attempts/{aid}/submit")
    pending = student_client.get(f"/api/attempts/{aid}/results").json()
    assert pending["scoring_status"] == "Pending" and pending["pending_segments"] == 2
    jobs.run_until_empty()
    r = student_client.get(f"/api/attempts/{aid}/results").json()
    assert r["scoring_status"] == "Completed" and r["total_score"] == 41.5 and r["result"] == "Pass"
    assert r["deductions"] == {"accuracy": 3, "language": 0, "fluency": 0.5, "total": 3.5}
    assert r["demo_scoring"] is True
    seg = r["dialogues"][0]["segments"][0]
    assert seg["transcript"] == "Reference 1.1" and seg["source_transcript"] == "Source transcript 1"
    assert [a["result"] for a in seg["accuracy"]] == ["Correct", "Omission"] and seg["accuracy"][1]["deduction"] == 1
    assert seg["accuracy"][1]["suggested_version"] == "Reference 1.2"
    assert seg["fluency"][0]["type"] == "Pause" and seg["has_recording"]
    assert "stt_words" not in seg  # admin-only detail
    assert r["history"][0]["id"] == aid
