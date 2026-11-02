"""Dashboard performance summary (Round 1 revision): averages over the last N attempts, per topic and per difficulty,
compared with the markers in ccl.yaml. Everything here is arithmetic on scores the scoring engine already produced."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AttemptResult, AttemptStatus, Difficulty, RecordStatus, Topic
from ..settings import ccl_config
from . import score_visibility as gate

FOCUS_TOPICS = 3


def _mean(scores: list[float]) -> float | None:
    return round(sum(scores) / len(scores), 1) if scores else None


def markers() -> dict:
    return ccl_config()["dashboard"]["score_markers"]


def outcome(summary: dict) -> str | None:
    """Which Recent Attempts tab a finished, visible attempt is listed under: "passed" or "other"."""
    if summary["total_score"] is None or summary["status"] == AttemptStatus.IN_PROGRESS.value:
        return None
    if summary["kind"] == "mock":
        return "passed" if summary["result"] == AttemptResult.PASS.value else "other"
    return "passed" if summary["total_score"] >= markers()["pass"] else "other"


def _message(last_mock_passed: bool | None, difficult: float | None, has_scores: bool) -> dict:
    if last_mock_passed is True:
        if difficult is not None and difficult < markers()["pass"]:
            return {"title": "Almost There!", "text": "You passed your last mock test. You just need to be more "
                    "consistent, especially with difficult dialogues."}
        return {"title": "Keep It Up!", "text": "You passed your last mock test. Keep practising to stay consistent."}
    if last_mock_passed is False:
        return {"title": "Keep Going", "text": "Your last mock test did not reach the pass mark. Work on the topics "
                "below, then try another one."}
    if has_scores:
        return {"title": "Ready for a Mock Test?", "text": "Take a full mock test to see how you do with two "
                "dialogues under test conditions."}
    return {"title": "Get Started", "text": "Practise your first dialogue. Your results will appear here."}


def summary(db: Session, refs: list, staff: bool, last_n: int | None) -> dict:
    """refs: the student's attempts, newest first."""
    def shown(da) -> bool:
        return staff or gate.is_validated(gate.pair_code(da.dialogue.language_pair))

    mocks = [r.mock for r in refs if r.mock and r.mock.total_score is not None and shown(r.dialogue_attempts[0])]
    # Mock test dialogues count for difficulty, as they are dialogues the student did; topics are practice only.
    attempts = [da for r in refs for da in r.dialogue_attempts if da.total_score is not None and shown(da)]
    by_difficulty = {level: [da.total_score for da in attempts if da.dialogue.difficulty == level][:last_n]
                     for level in (Difficulty.EASY, Difficulty.DIFFICULT)}
    practice = [da for da in attempts if da.mock_test_attempt_id is None]

    rows = db.scalars(select(Topic).where(Topic.status == RecordStatus.ACTIVE).order_by(Topic.sort_order, Topic.name))
    categories = []
    for t in rows:
        scores = [da.total_score for da in practice if da.dialogue.topic_id == t.id][:last_n]
        categories.append({"topic": t.name, "average": _mean(scores), "count": len(scores)})
    scored = [c for c in categories if c["average"] is not None]
    focus = sorted((c for c in scored if c["average"] < markers()["pass"]), key=lambda c: c["average"])[:FOCUS_TOPICS]

    difficult = _mean(by_difficulty[Difficulty.DIFFICULT])
    last_mock_passed = mocks[0].result == AttemptResult.PASS if mocks and mocks[0].result else None
    return {
        "total_average": _mean([m.total_score for m in mocks[:last_n]]), "mocks_counted": len(mocks[:last_n]),
        "easy_average": _mean(by_difficulty[Difficulty.EASY]), "difficult_average": difficult,
        "categories": categories, "focus": focus, "markers": markers(),
        "message": _message(last_mock_passed, difficult, bool(attempts)),
    }
