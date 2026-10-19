import pytest

from app.services.media_pipeline import run_ffmpeg
from app.services.scoring import timing
from app.settings import scoring_config

CFG = scoring_config()["timing"]


def synth(path, parts):
    """parts: [("silence"|"tone", seconds), ...] -> wav file."""
    inputs, labels = [], []
    for i, (kind, secs) in enumerate(parts):
        src = f"sine=frequency=300:duration={secs}" if kind == "tone" else f"anullsrc=r=16000:cl=mono:d={secs}"
        inputs += ["-f", "lavfi", "-i", src]
        labels.append(f"[{i}]aresample=16000,aformat=channel_layouts=mono[a{i}]")
    filt = ";".join(labels) + ";" + "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    run_ffmpeg([*inputs, "-filter_complex", filt, "-map", "[out]", str(path)])
    return path


def test_start_delay_and_pause_from_audio(tmp_path):
    wav = synth(tmp_path / "a.wav", [("silence", 5.6), ("tone", 1.0), ("silence", 3.6), ("tone", 1.0),
                                     ("silence", 1.0), ("tone", 0.8)])
    r = timing.analyse(wav, [], "", {"chime_end_ms": 1000, "record_start_ms": 1100}, CFG, [])
    assert r.method == "vad" and len(r.speech_regions) == 3
    assert r.speech_start == pytest.approx(5.7, abs=0.1)  # 5.6 s silence + 0.1 s recorder start gap
    types = [e.type for e in r.events]
    assert types == ["StartDelay", "Pause"]  # the 1.0 s gap is a normal short pause
    assert r.events[1].duration == pytest.approx(3.6, abs=0.1)


def test_no_events_for_fluent_answer(tmp_path):
    wav = synth(tmp_path / "b.wav", [("silence", 1.2), ("tone", 2.0), ("silence", 0.8), ("tone", 1.5)])
    r = timing.analyse(wav, [], "", {}, CFG, [])
    assert r.events == [] and r.speech_start == pytest.approx(1.2, abs=0.1)


def test_word_timestamp_fallback_and_thresholds_from_config():
    words = [{"word": "Ang", "start": 6.0, "end": 6.3}, {"word": "appointment", "start": 6.3, "end": 7.0},
             {"word": "ay", "start": 10.5, "end": 10.7}]
    r = timing.analyse(None, words, "Ang appointment ay", {}, CFG, [])
    assert r.method == "words" and [e.type for e in r.events] == ["StartDelay", "Pause"]
    relaxed = {**CFG, "start_delay_seconds": 7, "long_pause_seconds": 4}
    assert timing.analyse(None, words, "", {}, relaxed, []).events == []


def test_silent_recording_has_no_speech(tmp_path):
    wav = synth(tmp_path / "c.wav", [("silence", 3.0)])
    r = timing.analyse(wav, [], "", {}, CFG, [])
    assert r.speech_regions == [] and r.speech_start is None and r.events == []


def test_filler_candidates():
    words = [{"word": "Ano,", "start": 1.0}, {"word": "ang", "start": 1.2}, {"word": "uh", "start": 2.0}]
    found = timing.filler_candidates(words, "Ano, ang uh... ano ba yung", ["ano", "uh", "ano ba"])
    assert [f["text"] for f in found] == ["ano", "uh", "ano ba"]
