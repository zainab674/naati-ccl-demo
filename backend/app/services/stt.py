"""Speech-to-text behind one interface. Groq Whisper Large V3 Turbo by default (word timestamps), with a fallback
model from env; "mock" for development without keys (clearly labelled as such in results)."""
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from ..settings import get_settings
from .media_pipeline import run_ffmpeg

log = logging.getLogger("stt")


class STTError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Transcript:
    text: str
    words: list[dict] = field(default_factory=list)  # [{"word", "start", "end"}] seconds from recording start
    language: str | None = None
    confidence: float | None = None                  # 0..1 from Whisper avg_logprob
    no_speech_prob: float | None = None
    provider: str = ""
    model: str = ""
    raw: dict = field(default_factory=dict)


def normalise_audio(src: Path, dest: Path) -> Path:
    """Any browser recording -> 16 kHz mono FLAC (small, exact duration, what Whisper resamples to anyway)."""
    run_ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "flac", str(dest)])
    return dest


class STTProvider:
    name = "base"

    def transcribe(self, audio: Path, language: str | None, prompt: str = "") -> Transcript:
        raise NotImplementedError


class GroqProvider(STTProvider):
    name = "groq"

    def _call(self, model: str, audio: Path, language: str | None, prompt: str) -> Transcript:
        import openai

        client = openai.OpenAI(api_key=get_settings().groq_api_key, base_url="https://api.groq.com/openai/v1",
                               max_retries=1, timeout=120)
        kwargs = {"model": model, "response_format": "verbose_json", "timestamp_granularities": ["word", "segment"],
                  "temperature": 0}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt[:800]  # vocabulary hint only (names, terms); never the expected answer
        try:
            with audio.open("rb") as f:
                result = client.audio.transcriptions.create(file=(audio.name, f), **kwargs)
        except openai.RateLimitError as e:
            raise STTError(f"Groq rate limited: {e}") from e
        except openai.APIStatusError as e:
            raise STTError(f"Groq error {e.status_code}: {e.message}", retryable=e.status_code >= 500) from e
        except openai.APIConnectionError as e:
            raise STTError(f"Could not reach Groq: {e}") from e
        data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        return parse_verbose_json(data, self.name, model)

    def transcribe(self, audio, language, prompt=""):
        s = get_settings()
        try:
            return self._call(s.stt_model, audio, language, prompt)
        except STTError as e:
            if not s.stt_fallback_model or s.stt_fallback_model == s.stt_model:
                raise
            log.warning("STT model %s failed (%s); trying fallback %s", s.stt_model, e, s.stt_fallback_model)
            return self._call(s.stt_fallback_model, audio, language, prompt)


# Whisper's verbose_json reports a language name; store the ISO code we send as the hint (Language.stt_code).
WHISPER_LANGUAGE_CODES = {"english": "en", "tagalog": "tl", "filipino": "tl", "hindi": "hi", "chinese": "zh",
                          "mandarin": "zh", "punjabi": "pa", "panjabi": "pa", "arabic": "ar", "nepali": "ne",
                          "vietnamese": "vi"}


def parse_verbose_json(data: dict, provider: str, model: str) -> Transcript:
    words = [{"word": (w.get("word") or "").strip(), "start": float(w.get("start") or 0), "end": float(w.get("end") or 0)}
             for w in (data.get("words") or [])]
    segs = data.get("segments") or []
    logprobs = [s["avg_logprob"] for s in segs if s.get("avg_logprob") is not None]
    no_speech = [s["no_speech_prob"] for s in segs if s.get("no_speech_prob") is not None]
    lang = (data.get("language") or "").lower() or None
    lang = WHISPER_LANGUAGE_CODES.get(lang, lang)
    return Transcript(text=(data.get("text") or "").strip(), words=words, language=lang,
                      confidence=round(math.exp(sum(logprobs) / len(logprobs)), 3) if logprobs else None,
                      no_speech_prob=round(max(no_speech), 3) if no_speech else None,
                      provider=provider, model=model, raw=data)


class MockProvider(STTProvider):
    """No network. Returns a fixed text set by the caller (dev: the reference interpretation) with even word timings
    starting 1 s into the recording. Results produced this way are labelled "mock" everywhere."""
    name = "mock"
    override: str | None = None  # tests set this to simulate what the student said

    def __init__(self, text: str = ""):
        self.text = text

    def transcribe(self, audio, language, prompt=""):
        text = MockProvider.override if MockProvider.override is not None else self.text
        words, t = [], 1.0
        for w in text.split():
            words.append({"word": w, "start": round(t, 2), "end": round(t + 0.35, 2)})
            t += 0.45
        return Transcript(text=text, words=words, language=language, confidence=0.9 if text else None,
                          provider=self.name, model="mock")


def get_stt(mock_text: str = "") -> STTProvider:
    return GroqProvider() if get_settings().resolved_stt == "groq" else MockProvider(mock_text)
