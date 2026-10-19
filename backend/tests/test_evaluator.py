import json

import pytest
from sqlalchemy import select

from app.models import Language, LanguageScoringConfig
from app.services.ai.llm import LLMError, LLMProvider, LLMResult, strict_schema
from app.services.scoring import evaluator

from .factories import make_dialogue


class ScriptedLLM(LLMProvider):
    name = "scripted"

    def __init__(self, *responses):
        super().__init__("scripted-model")
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, system, user, schema, schema_name="result"):
        self.prompts.append((system, user, schema))
        return LLMResult(self.responses.pop(0), self.name, self.model)


def good(mu_numbers=(1, 2)):
    return {"meaning_units": [{"meaning_unit": n, "result": "correct" if n == 1 else "distortion",
                               "student_interpretation": "sa Martes" if n == 1 else "alas-diyes",
                               "explanation": "x", "suggested_version": "y", "confidence": 0.9} for n in mu_numbers],
            "insertions": [{"student_text": "ng umaga", "explanation": "added morning", "confidence": 0.8}],
            "language_quality": [{"error": "grammar", "student_text": "ay sa", "suggested_version": "ay sa", "explanation": "e", "confidence": 0.7}],
            "fluency": [{"error": "self_correction", "transcript_excerpt": "Lunes, Martes", "explanation": "e", "confidence": 0.8}],
            "transcript_quality": "good", "overall_feedback": "Good.", "confidence": 0.85}


def segment(db):
    d = make_dialogue(db, segments=1, mus_per_segment=2)
    return d.segments[0]


def test_schema_has_no_scores():
    text = json.dumps(evaluator.Evaluation.model_json_schema()).lower()
    assert "score" not in text and "deduction" not in text and "points" not in text
    s = strict_schema(evaluator.Evaluation.model_json_schema())
    assert "minimum" not in json.dumps(s) and s["additionalProperties"] is False


def test_prompt_contents_and_language_guidance(db):
    seg = segment(db)
    fil = db.scalar(select(Language).where(Language.code == "fil"))
    cfg = db.scalar(select(LanguageScoringConfig).where(LanguageScoringConfig.language_id == fil.id))
    req = evaluator.build_request(seg, "Ang appointment mo ay sa Martes", [{"text": "ano"}], cfg)
    assert "from English into Filipino" in req["system"] and "Taglish" in req["system"]
    assert "never give marks or scores" in req["system"]
    user = json.loads(req["user"])
    assert [m["meaning_unit"] for m in user["meaning_units"]] == [1, 2] and user["candidate_filler_words"] == ["ano"]
    assert req["mu_numbers"] == [1, 2]


def test_retry_when_a_meaning_unit_is_missing(db):
    seg = segment(db)
    llm = ScriptedLLM(good(mu_numbers=(1,)), good())
    out = evaluator.evaluate(seg, "sa Martes alas-diyes ng umaga ay sa Lunes, Martes", [], None, llm=llm)
    assert len(out.results) == 2 and "[2] were not evaluated" in llm.prompts[1][1]
    assert [m.result for m in out.evaluation.meaning_units] == ["correct", "distortion"]
    assert out.quote_problems == []


def test_invalid_output_raises_after_retries(db):
    seg = segment(db)
    bad = {**good(), "meaning_units": [{"meaning_unit": 1, "result": "great"}]}
    with pytest.raises(LLMError):
        evaluator.evaluate(seg, "x", [], None, llm=ScriptedLLM(bad, bad))


def test_quotes_not_in_transcript_are_flagged(db):
    seg = segment(db)
    out = evaluator.evaluate(seg, "completely different words", [], None, llm=ScriptedLLM(good()))
    assert "sa Martes" in out.quote_problems


def test_mock_evaluation_matches_references(db):
    seg = segment(db)
    out = evaluator.evaluate(seg, "Reference 1.1 and something else", [], None)
    assert out.last.provider == "mock"
    assert [m.result for m in out.evaluation.meaning_units] == ["correct", "omission"]
