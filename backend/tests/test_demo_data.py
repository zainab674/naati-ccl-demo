"""The demo data loader (app/demo_data.py): refuses production; its stand-in evaluator plants each kind of error."""
import json

import pytest

from app import demo_data
from app.services.scoring.evaluator import Evaluation


def test_refuses_production(monkeypatch):
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(SystemExit, match="production"):
        demo_data.main()


def test_demo_content_is_marked_and_uses_example_addresses():
    from app import demo_content as C

    assert all(d["key"].startswith("demo-") and d["title"].startswith("DEMO") for d in C.DIALOGUES)
    assert all(s["email"].endswith("@example.com") for s in C.STUDENTS)
    assert {d["lote"] for d in C.DIALOGUES} == {"fil", "hi", "zh", "pa", "ar", "ne", "vi"}


def test_stand_in_evaluator_output_is_valid_and_covers_each_error():
    ref = "Gusto po ng landlord ninyo na kunin ang 400 dolyar mula sa inyong bond"
    mus = [{"meaning_unit": 1, "meaning": "Landlord keeps $400", "reference_rendering": ref},
           {"meaning_unit": 2, "meaning": "Works in the morning", "reference_rendering": "I work in the mornings"},
           {"meaning_unit": 3, "meaning": "For cleaning", "reference_rendering": "Para sa paglilinis"}]
    said = "um um gusto po ng landlord ninyo na kunin ang 40 dolyar mula sa inyong bond i working in the mornings"
    out = demo_data._demo_evaluator("", json.dumps({"candidate_transcript": said, "meaning_units": mus}), {})
    Evaluation.model_validate(out)  # same schema the real evaluator must meet
    assert [m["result"] for m in out["meaning_units"]] == ["distortion", "correct", "omission"]
    assert [x["error"] for x in out["language_quality"]] == ["grammar"]
    assert [x["error"] for x in out["fluency"]] == ["hesitation"]


def test_speech_like_audio_has_the_planned_start_delay(tmp_path):
    from app.services.scoring import timing

    wav = tmp_path / "a.wav"
    demo_data.speech_like_wav(wav, 8, lead=6.5, seed=1)
    from app.settings import scoring_config
    result = timing.analyse(wav, [], "", {}, scoring_config()["timing"], [])
    assert any(e.type == "StartDelay" for e in result.events)
