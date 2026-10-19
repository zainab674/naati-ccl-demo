"""AI helper for admins: suggest Meaning Units for a segment. Suggestions are never saved automatically."""
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...models import Segment
from ...settings import BASE_DIR
from .llm import LLMError, get_llm

PROMPT_VERSION = "suggest_meaning_units_v1"


class SuggestedMU(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meaning: str = Field(min_length=1)
    reference_interpretation: str


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meaning_units: list[SuggestedMU] = Field(min_length=1, max_length=20)


def _mock(system: str, user: str, schema: dict) -> dict:
    """Offline fallback: one MU per clause of the transcript."""
    source = user.split("SOURCE SEGMENT:", 1)[-1].strip().splitlines()[0]
    parts = [p.strip() for p in re.split(r"[,.;?!]| and | at | on | in ", source) if p.strip()]
    return {"meaning_units": [{"meaning": p, "reference_interpretation": ""} for p in parts or [source]]}


def suggest(segment: Segment) -> dict:
    system = (BASE_DIR / "app" / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8").replace(
        "{target_language}", segment.target_language.name)
    user = (f"SOURCE SEGMENT: {segment.transcript}\n"
            f"Source language: {segment.source_language.name}. Target language: {segment.target_language.name}.")
    llm = get_llm(mock_fallback=_mock)
    try:
        result = llm.generate_json(system, user, Suggestion.model_json_schema(), "meaning_units")
        parsed = Suggestion.model_validate(result.data)
    except ValidationError as e:
        raise LLMError(f"Model output did not match the schema: {e.errors()[:2]}") from e
    return {"provider": result.provider, "model": result.model, "prompt_version": PROMPT_VERSION,
            "meaning_units": [{"meaning_unit_number": i, **m.model_dump()}
                              for i, m in enumerate(parsed.meaning_units, start=1)]}
