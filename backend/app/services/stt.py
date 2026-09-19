"""Speech-to-text behind one function so the provider can be swapped.

transcribe() returns text, word timestamps (when available) and a 0..1
confidence. The "mock" provider exists so the demo runs without keys: it
returns the segment's sample answer and is clearly labelled as mock in the UI.
"""
import math
from dataclasses import dataclass, field
from pathlib import Path

from ..settings import get_settings


@dataclass
class Transcript:
    text: str
    words: list[dict] = field(default_factory=list)  # [{"word", "start", "end"}]
    confidence: float | None = None
    provider: str = ""
    language: str | None = None  # detected by the STT provider, when it reports one


def transcribe(audio_path: Path, language: str, mock_text: str = "") -> Transcript:
    provider = get_settings().resolved_stt
    if provider in ("openai", "groq"):
        return _whisper_api(audio_path, language, provider)
    return Transcript(text=mock_text, words=[], confidence=None, provider="mock")


def _whisper_api(audio_path: Path, language: str, provider: str) -> Transcript:
    from openai import OpenAI  # speech-to-text only; marking uses Claude

    s = get_settings()
    if provider == "groq":
        client = OpenAI(api_key=s.groq_api_key, base_url="https://api.groq.com/openai/v1")
        model = "whisper-large-v3"
    else:
        client = OpenAI(api_key=s.openai_api_key)
        model = "whisper-1"

    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=model,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )
    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    words = [
        {"word": w.get("word", ""), "start": w.get("start", 0.0), "end": w.get("end", 0.0)}
        for w in (data.get("words") or [])
    ]
    segs = data.get("segments") or []
    confidence = None
    if segs:
        logprobs = [s.get("avg_logprob") for s in segs if s.get("avg_logprob") is not None]
        if logprobs:
            confidence = round(math.exp(sum(logprobs) / len(logprobs)), 3)
    # Whisper reports full names ("english", "hindi") on some providers, codes on others.
    lang = (data.get("language") or "").lower()
    lang = {"english": "en", "hindi": "hi", "urdu": "ur"}.get(lang, lang) or None
    return Transcript(text=(data.get("text") or "").strip(), words=words,
                      confidence=confidence, provider=provider, language=lang)
