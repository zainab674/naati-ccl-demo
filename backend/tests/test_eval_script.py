from scripts import eval_against_teacher as ev
from app.services.media_pipeline import run_ffmpeg

from .factories import make_dialogue


def test_eval_script_compares_ai_and_teacher(db, tmp_path, capsys):
    make_dialogue(db, key="eval-d", segments=2, mus_per_segment=2)
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=300:duration=1.5", "-c:a", "libopus", str(tmp_path / "s3.webm")])
    (tmp_path / "samples.csv").write_text(
        "sample_id,dialogue_key,segment_no,audio_path,teacher_accuracy,teacher_language,teacher_fluency,transcript\n"
        "S1,eval-d,1,,0,0,0,Reference 1.1 Reference 1.2\n"
        "S2,eval-d,2,,1,0.5,0,Reference 2.1\n"
        "S3,eval-d,1,s3.webm,0,0,0,\n", encoding="utf-8")
    ev.main([str(tmp_path / "samples.csv"), "--out", str(tmp_path / "report.csv")])
    out = capsys.readouterr().out
    assert "S1" in out and "mean |AI - teacher|" in out
    report = (tmp_path / "report.csv").read_text(encoding="utf-8").splitlines()
    assert report[0].startswith("sample_id,ai_accuracy") and len(report) == 4
    s2 = report[2].split(",")
    assert s2[1] == "1.0" and s2[5] == "1.0"  # AI and teacher both -1 accuracy (mock evaluator: MU 2 missing)
    summ = ev.summary([ev.SampleResult("x", ev.engine.Totals(1, 0, 0), ev.engine.Totals(0, 0.5, 0), "", "")])
    assert summ["accuracy"]["mean_diff"] == 1 and summ["language"]["within_0_5"] == 1
