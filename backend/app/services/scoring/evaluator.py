"""Pipeline step 3: the AI evaluator. It identifies and classifies errors; it never returns scores.

The request (source, Meaning Units, transcript, language guidance) and the model's raw output are stored in
AIScoringRun by the caller. Output is validated with Pydantic, and every active Meaning Unit must be evaluated
exactly once; otherwise the model is asked again with the problem spelled out.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...models import LanguageScoringConfig, Segment
from ...settings import BASE_DIR
from ..ai.llm import LLMError, LLMProvider, LLMResult, get_llm

PROMPT_VERSION = "evaluate_segment_v1"
MAX_TRIES = 2


class MUItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meaning_unit: int
    result: Literal["correct", "omission", "distortion"]
    student_interpretation: str
    explanation: str
    suggested_version: str
    confidence: float = Field(ge=0, le=1)


class InsertionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_text: str
    explanation: str
    confidence: float = Field(ge=0, le=1)


class LanguageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: Literal["grammar", "unidiomatic_usage", "register", "sentence_structure", "pronunciation"]
    student_text: str
    suggested_version: str
    explanation: str
    confidence: float = Field(ge=0, le=1)


class FluencyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: Literal["hesitation", "self_correction"]
    transcript_excerpt: str
    explanation: str
    confidence: float = Field(ge=0, le=1)


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meaning_units: list[MUItem]
    insertions: list[InsertionItem]
    language_quality: list[LanguageItem]
    fluency: list[FluencyItem]
    transcript_quality: Literal["good", "uncertain", "poor"]
    overall_feedback: str
    confidence: float = Field(ge=0, le=1)


@dataclass
class EvaluationOutcome:
    evaluation: Evaluation
    request: dict
    results: list[LLMResult] = field(default_factory=list)  # one per try
    quote_problems: list[str] = field(default_factory=list)

    @property
    def last(self) -> LLMResult:
        return self.results[-1]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'-]", " ", (s or "").lower())).strip()


def build_request(segment: Segment, transcript: str, fillers: list[dict], config: LanguageScoringConfig | None) -> dict:
    mus = [m for m in segment.meaning_units if m.active]
    guidance = ""
    if config:
        parts = [("Grammar guidance", config.grammar_guidelines), ("Register guidance", config.register_guidelines),
                 ("Additional guidance", config.ai_prompt_addition)]
        guidance = "## Guidance for " + segment.target_language.name + "\n" + "\n".join(
            f"- {label}: {text}" for label, text in parts if text)
    system = (BASE_DIR / "app" / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8").format(
        source_language=segment.source_language.name, target_language=segment.target_language.name,
        language_guidance=guidance)
    user = {
        "source_segment": segment.transcript,
        "meaning_units": [{"meaning_unit": m.meaning_unit_number, "meaning": m.meaning,
                           "reference_rendering": m.reference_interpretation} for m in mus],
        "candidate_transcript": transcript,
        "candidate_filler_words": [f["text"] for f in fillers],
    }
    return {"system": system, "user": json.dumps(user, ensure_ascii=False, indent=1),
            "mu_numbers": [m.meaning_unit_number for m in mus]}


def coverage_problem(ev: Evaluation, mu_numbers: list[int]) -> str:
    got = [m.meaning_unit for m in ev.meaning_units]
    missing = sorted(set(mu_numbers) - set(got))
    extra = sorted(set(got) - set(mu_numbers))
    dupes = sorted({n for n in got if got.count(n) > 1})
    problems = []
    if missing:
        problems.append(f"Meaning units {missing} were not evaluated.")
    if extra:
        problems.append(f"Meaning units {extra} do not exist.")
    if dupes:
        problems.append(f"Meaning units {dupes} were evaluated more than once.")
    return " ".join(problems)


def quote_problems(ev: Evaluation, transcript: str) -> list[str]:
    """Quotes that do not appear in the transcript (kept, but the segment is flagged for review)."""
    t = _norm(transcript)
    quotes = [m.student_interpretation for m in ev.meaning_units] + [i.student_text for i in ev.insertions] + \
             [i.student_text for i in ev.language_quality] + [i.transcript_excerpt for i in ev.fluency]
    return [q for q in quotes if q and _norm(q) and _norm(q) not in t]


def mock_evaluation(request: dict) -> dict:
    """Keyless dev: an MU counts as correct when its reference rendering appears in the transcript."""
    data = json.loads(request["user"])
    t = _norm(data["candidate_transcript"])
    items = []
    for m in data["meaning_units"]:
        ref = _norm(m["reference_rendering"])
        ok = bool(ref) and ref in t
        items.append({"meaning_unit": m["meaning_unit"], "result": "correct" if ok else "omission",
                      "student_interpretation": m["reference_rendering"] if ok else "",
                      "explanation": "" if ok else f'"{m["meaning"]}" was not found in your interpretation.',
                      "suggested_version": m["reference_rendering"], "confidence": 0.5})
    return {"meaning_units": items, "insertions": [], "language_quality": [], "fluency": [],
            "transcript_quality": "uncertain", "confidence": 0.5,
            "overall_feedback": "Development mode: this feedback comes from a simple text match, not the AI evaluator."}


def evaluate(segment: Segment, transcript: str, fillers: list[dict], config: LanguageScoringConfig | None,
             llm: LLMProvider | None = None) -> EvaluationOutcome:
    request = build_request(segment, transcript, fillers, config)
    llm = llm or get_llm(mock_fallback=lambda system, user, schema: mock_evaluation(request))
    schema = Evaluation.model_json_schema()
    user = request["user"]
    outcome_results: list[LLMResult] = []
    last_error = ""
    for _ in range(MAX_TRIES):
        prompt = user if not last_error else (
            user + f"\n\nYour previous answer was rejected: {last_error} Return the full corrected JSON.")
        result = llm.generate_json(request["system"], prompt, schema, "segment_evaluation")
        outcome_results.append(result)
        try:
            ev = Evaluation.model_validate(result.data)
        except ValidationError as e:
            last_error = f"It did not match the schema ({e.errors()[0]['loc']}: {e.errors()[0]['msg']})."
            continue
        problem = coverage_problem(ev, request["mu_numbers"])
        if problem:
            last_error = problem
            continue
        return EvaluationOutcome(ev, request, outcome_results, quote_problems(ev, transcript))
    err = LLMError(f"Evaluator output rejected after {MAX_TRIES} tries: {last_error}")
    err.raw = {"tries": [r.data for r in outcome_results]}
    raise err
