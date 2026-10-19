"""LLM providers behind one interface: generate_json(system, user, schema) -> validated JSON dict.

Gemini (default, Flash-Lite), Anthropic and OpenAI are interchangeable via EVALUATOR_PROVIDER; model names come from
settings. "mock" is for development and tests without keys. Callers validate the result with Pydantic and never ask
a model for a score.
"""
import copy
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from ...settings import get_settings

log = logging.getLogger("llm")


class LLMError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True, raw: dict | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.raw = raw or {}


@dataclass
class LLMResult:
    data: dict
    provider: str
    model: str
    raw: dict = field(default_factory=dict)


def strict_schema(schema: dict) -> dict:
    """Inline $defs and require additionalProperties: false on every object (needed for strict JSON modes)."""
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].rsplit("/", 1)[-1]]))
            node = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            return node
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


class LLMProvider:
    name = "base"

    def __init__(self, model: str):
        self.model = model

    def generate_json(self, system: str, user: str, schema: dict, schema_name: str = "result") -> LLMResult:
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    name = "gemini"

    def generate_json(self, system, user, schema, schema_name="result"):
        from google import genai
        from google.genai import errors, types

        client = genai.Client(api_key=get_settings().gemini_api_key)
        try:
            resp = client.models.generate_content(
                model=self.model, contents=user,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0,
                                                   response_mime_type="application/json",
                                                   response_json_schema=strict_schema(schema)))
        except errors.ClientError as e:  # 4xx: bad request / key; 429 is retryable
            raise LLMError(f"Gemini error {e.code}: {e.message}", retryable=e.code == 429) from e
        except errors.APIError as e:  # 5xx and other server-side failures
            raise LLMError(f"Gemini error {getattr(e, 'code', '')}: {e}") from e
        raw = resp.model_dump(mode="json", exclude_none=True)
        try:
            return LLMResult(json.loads(resp.text or ""), self.name, self.model, raw)
        except json.JSONDecodeError as e:
            raise LLMError("Gemini returned invalid JSON", raw=raw) from e


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def generate_json(self, system, user, schema, schema_name="result"):
        import anthropic

        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
        try:
            resp = client.beta.messages.create(
                model=self.model, max_tokens=16000, system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "medium",
                               "format": {"type": "json_schema", "schema": strict_schema(schema)}},
                # Refusals are re-routed server-side instead of failing the scoring run.
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except anthropic.RateLimitError as e:
            raise LLMError(f"Anthropic rate limited: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic error {e.status_code}: {e.message}", retryable=e.status_code >= 500) from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Could not reach Anthropic: {e}") from e
        raw = resp.model_dump(mode="json")
        if resp.stop_reason == "refusal":
            raise LLMError("Model declined the request", retryable=False, raw=raw)
        if resp.stop_reason == "max_tokens":
            raise LLMError("Model output was cut off (max_tokens)", raw=raw)
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return LLMResult(json.loads(text), self.name, resp.model, raw)
        except json.JSONDecodeError as e:
            raise LLMError("Anthropic returned invalid JSON", raw=raw) from e


class OpenAIProvider(LLMProvider):
    name = "openai"

    def generate_json(self, system, user, schema, schema_name="result"):
        import openai

        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema", "json_schema": {
                    "name": schema_name, "schema": strict_schema(schema), "strict": True}})
        except openai.RateLimitError as e:
            raise LLMError(f"OpenAI rate limited: {e}") from e
        except openai.APIStatusError as e:
            raise LLMError(f"OpenAI error {e.status_code}: {e.message}", retryable=e.status_code >= 500) from e
        except openai.APIConnectionError as e:
            raise LLMError(f"Could not reach OpenAI: {e}") from e
        raw = resp.model_dump(mode="json")
        try:
            return LLMResult(json.loads(resp.choices[0].message.content or ""), self.name, resp.model, raw)
        except json.JSONDecodeError as e:
            raise LLMError("OpenAI returned invalid JSON", raw=raw) from e


class MockProvider(LLMProvider):
    """No network. Returns what the caller's mock function builds from the request (or an empty result)."""
    name = "mock"
    responder: Callable[[str, str, dict], dict] | None = None  # tests may set a global responder

    def __init__(self, model: str = "mock", fallback: Callable[[str, str, dict], dict] | None = None):
        super().__init__(model)
        self.fallback = fallback

    def generate_json(self, system, user, schema, schema_name="result"):
        fn = MockProvider.responder or self.fallback
        data = fn(system, user, schema) if fn else {}
        return LLMResult(data, self.name, self.model, {"mock": True})


def get_llm(mock_fallback: Callable[[str, str, dict], dict] | None = None) -> LLMProvider:
    s = get_settings()
    provider = s.resolved_evaluator
    if provider == "gemini":
        return GeminiProvider(s.gemini_model)
    if provider == "anthropic":
        return AnthropicProvider(s.anthropic_model)
    if provider == "openai":
        return OpenAIProvider(s.openai_model)
    return MockProvider(fallback=mock_fallback)
