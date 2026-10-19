import pytest

from app.services import stt
from app.services.media_pipeline import probe_duration, run_ffmpeg
from app.settings import get_settings

VERBOSE = {
    "text": " Ang appointment mo ay sa Martes. ", "language": "tagalog",
    "words": [{"word": "Ang", "start": 0.8, "end": 1.0}, {"word": "appointment", "start": 1.0, "end": 1.6}],
    "segments": [{"avg_logprob": -0.2, "no_speech_prob": 0.01}, {"avg_logprob": -0.4, "no_speech_prob": 0.05}],
}


def test_parse_verbose_json():
    t = stt.parse_verbose_json(VERBOSE, "groq", "whisper-large-v3-turbo")
    assert t.text == "Ang appointment mo ay sa Martes." and t.language == "tl"
    assert t.words[1] == {"word": "appointment", "start": 1.0, "end": 1.6}
    assert 0.7 < t.confidence < 0.8 and t.no_speech_prob == 0.05


def test_normalise_audio(tmp_path):
    src = tmp_path / "in.webm"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=500:duration=1.5", "-c:a", "libopus", str(src)])
    out = stt.normalise_audio(src, tmp_path / "out.flac")
    assert abs(probe_duration(out) - 1.5) < 0.1


@pytest.fixture
def groq_settings():
    s = get_settings()
    saved = (s.stt_provider, s.groq_api_key, s.stt_model, s.stt_fallback_model)
    s.stt_provider, s.groq_api_key = "groq", "gsk_test"
    yield s
    s.stt_provider, s.groq_api_key, s.stt_model, s.stt_fallback_model = saved


def test_groq_uses_turbo_then_fallback(groq_settings, monkeypatch, tmp_path):
    calls = []

    def fake_call(self, model, audio, language, prompt):
        calls.append((model, language))
        if model == "whisper-large-v3-turbo":
            raise stt.STTError("Groq error 503: overloaded")
        return stt.parse_verbose_json(VERBOSE, "groq", model)

    monkeypatch.setattr(stt.GroqProvider, "_call", fake_call)
    provider = stt.get_stt()
    assert isinstance(provider, stt.GroqProvider)
    t = provider.transcribe(tmp_path / "a.flac", "tl")
    assert calls == [("whisper-large-v3-turbo", "tl"), ("whisper-large-v3", "tl")] and t.model == "whisper-large-v3"


def test_groq_request_shape(groq_settings, monkeypatch, tmp_path):
    import openai

    captured = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type("R", (), {"model_dump": lambda self: VERBOSE})()

    class FakeClient:
        def __init__(self, **kw):
            captured["base_url"] = kw["base_url"]
            self.audio = type("A", (), {"transcriptions": FakeTranscriptions()})()

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    audio = tmp_path / "a.flac"
    audio.write_bytes(b"fLaC")
    t = stt.GroqProvider().transcribe(audio, "tl", prompt="Martes")
    assert captured["model"] == "whisper-large-v3-turbo" and captured["language"] == "tl"
    assert captured["timestamp_granularities"] == ["word", "segment"] and captured["response_format"] == "verbose_json"
    assert "groq.com" in captured["base_url"] and t.words


def test_mock_provider():
    t = stt.MockProvider("one two three").transcribe(None, "tl")
    assert t.provider == "mock" and t.words[0]["start"] == 1.0 and len(t.words) == 3


def test_transcribe_segment_stores_transcript_and_run(student_client, db, tmp_path):
    from sqlalchemy import select

    from app.models import AIScoringRun, SegmentAttempt
    from app.services.scoring.transcribe import transcribe_segment

    from .factories import make_dialogue

    d = make_dialogue(db, is_free=True, segments=1)
    aid = student_client.post("/api/attempts", json={"dialogue_id": str(d.id)}).json()["id"]
    sid = student_client.get(f"/api/attempts/{aid}/state").json()["dialogues"][0]["segments"][0]["segment_attempt_id"]
    student_client.post(f"/api/attempts/{aid}/segments/{sid}/play")
    webm = tmp_path / "a.webm"
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=500:duration=1", "-c:a", "libopus", str(webm)])
    student_client.post(f"/api/attempts/{aid}/segments/{sid}/recording", files={"audio": ("a.webm", webm.read_bytes(), "audio/webm")})
    sa = db.scalar(select(SegmentAttempt).where(SegmentAttempt.id == sid))
    t, flac = transcribe_segment(db, sa, tmp_path / "work")
    assert flac.exists() and t.provider == "mock" and t.text == "Reference 1.1 Reference 1.2"
    db.refresh(sa)
    assert sa.transcript_user == t.text and sa.stt_words and sa.stt_provider == "mock"
    run = db.scalar(select(AIScoringRun).where(AIScoringRun.kind == "stt"))
    assert run.status.value == "Success" and run.request_data["language"] == "tl"
