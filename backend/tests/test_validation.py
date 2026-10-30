"""Scoring validation study (validation/): statistics against textbook values, the report on a synthetic dataset,
Rasch recovery of a planted rater severity, the frozen split, the Label Studio import and the per-language gate.
Synthetic data here tests the harness only; it is never a result about the platform's accuracy."""
import json

import numpy as np
import pytest

from validation import dataset, gate, label_studio, metrics, rasch, report, split
from validation.ai_runs import AIItem, AIRecording

# ------------------------------------------------------------------ statistics


def test_icc_a1_matches_shrout_fleiss_example():
    # Shrout & Fleiss (1979) table 2: 6 targets x 4 judges; ICC(2,1) = 0.29 (= McGraw & Wong ICC(A,1)).
    y = np.array([[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]])
    assert metrics.icc_a1(y) == pytest.approx(0.290, abs=0.001)
    assert metrics.icc_a1(np.column_stack([y[:, 0], y[:, 0]])) == pytest.approx(1.0)


def test_quadratic_kappa_identical_and_chance():
    assert metrics.quadratic_weighted_kappa([0, 3, 5, 9], [0, 3, 5, 9], 0, 10) == pytest.approx(1.0)
    assert metrics.quadratic_weighted_kappa([0, 0, 1, 1], [0, 1, 0, 1], 0, 1) == pytest.approx(0.0)


def test_pass_fail_counts_false_passes():
    pf = metrics.pass_fail([True, True, False, True, False], [True, False, False, False, True])
    assert (pf["tp"], pf["fp"], pf["fn"], pf["tn"]) == (1, 2, 1, 1)
    assert pf["false_pass_rate"] == pytest.approx(2 / 3) and pf["false_pass_share"] == pytest.approx(2 / 3)


def test_error_matching_by_meaning_unit_and_time():
    E = metrics.ErrorItem
    ai = [E("r", "omission", 1), E("r", "distortion", 3), E("r", "grammar", None, 4.0, 4.6), E("r", "pause", None, 9, 13)]
    ex = [E("r", "omission", 1), E("r", "omission", 2), E("r", "grammar", None, 5.2, 5.5), E("r", "pause", None, 20, 24)]
    c = metrics.match_errors(ai, ex, tolerance=1.0)
    assert (c["omission"].tp, c["omission"].fn) == (1, 1)
    assert (c["distortion"].fp, c["grammar"].tp, c["pause"].fp, c["pause"].fn) == (1, 1, 1, 1)
    flag = metrics.mu_flag_counts(ai, ex)  # MU 1 agreed; MU 3 only AI; MU 2 only examiner
    assert (flag.tp, flag.fp, flag.fn) == (1, 1, 1)


def test_wer_and_quotes_normalise_case_and_punctuation():
    assert metrics.wer(["Ang appointment mo ay sa Martes."], ["ang appointment mo ay sa martes"]) == 0
    assert metrics.wer(["a b c d"], ["a x c d"]) == pytest.approx(0.25)
    assert metrics.quote_in_transcript("sa MARTES", "Ang appointment mo ay sa Martes.")
    assert not metrics.quote_in_transcript("sa Lunes", "Ang appointment mo ay sa Martes.")


def test_cluster_bootstrap_brackets_the_estimate():
    units = list(range(40))
    lo, hi = metrics.cluster_bootstrap(units, lambda u: f"s{u // 2}", lambda s: float(np.mean(s)), n_boot=500)
    assert lo < 19.5 < hi


# ------------------------------------------------------------------ synthetic dataset through the report

RNG = np.random.default_rng(11)


def write_dataset(root, students=12, segments=3, mus=3, examiners=("E1", "E2"), ai_severity=0.0):
    """Two dialogues per student (one test), 3 segments x 3 MUs each. Examiners mark MU misses drawn from the student's
    ability; the AI agrees with E1 except for extra misses controlled by ai_severity."""
    base = root / "fil"
    base.mkdir(parents=True)
    rec, ann, ai = ["recording_id,student_id,test_id,dialogue_key,segment_no,audio_path,consent"], [
        "recording_id,examiner_id,kind,error_type,mu_no,start_s,end_s,deduction,quote"], {}
    for s in range(students):
        ability = RNG.normal(0, 1.2)
        for d in ("d1", "d2"):
            for seg in range(1, segments + 1):
                rid = f"S{s}-{d}-{seg}"
                rec.append(f"{rid},S{s},T{s},{d},{seg},,yes")
                missed = [m for m in range(1, mus + 1) if RNG.random() > 1 / (1 + np.exp(-ability))]
                for e in examiners:
                    rows = [f"{rid},{e},accuracy,omission,{m},,,1," for m in missed]
                    ann += rows or [f"{rid},{e},none,,,,,,"]
                ai_missed = missed + [m for m in range(1, mus + 1) if m not in missed and RNG.random() < ai_severity]
                ai[rid] = AIRecording(rid, "texto", 0.4, [], [AIItem("omission", m) for m in ai_missed],
                                      {"accuracy": float(len(ai_missed)), "language": 0.0, "fluency": 0.0}, mu_count=mus)
    (base / "recordings.csv").write_text("\n".join(rec) + "\n")
    (base / "annotations.csv").write_text("\n".join(ann) + "\n")
    return base, ai


def test_report_on_synthetic_data_identical_raters(tmp_path):
    _, ai = write_dataset(tmp_path)
    ds = dataset.load("fil", tmp_path)
    rep = report.build(ds, ai, list(ds.recordings), "dev", {"key": "test"}, n_boot=200)
    t = rep["dialogue_totals"]
    assert t["units"] == 24 and t["examiner_vs_examiner_icc"]["value"] == pytest.approx(1.0)
    assert t["ai_vs_examiner_icc"]["value"] == pytest.approx(1.0) and t["bland_altman"]["bias"] == pytest.approx(0)
    assert rep["errors"]["omission"]["ai"]["precision"] == 1 and rep["pass_fail_test_63"]["n"] == 12
    checks = {c["check"]: c["passed"] for c in rep["bar"]["checks"]}
    assert checks["enough dialogue attempts"] is False      # 24 < 40: not a pass however good the numbers look
    assert checks["false-pass rate at 63"] in (True, None)
    assert rep["bar"]["passed"] is False and "# Scoring validation: fil (dev)" in report.to_markdown(rep)


def test_report_shows_a_harsh_ai_as_bias_and_lost_precision(tmp_path):
    _, ai = write_dataset(tmp_path, students=20, ai_severity=0.5)
    ds = dataset.load("fil", tmp_path)
    rep = report.build(ds, ai, list(ds.recordings), "dev", {"key": "test"}, n_boot=200)
    t = rep["dialogue_totals"]
    assert t["bland_altman"]["bias"] < -1          # AI gives lower marks
    assert t["icc_gap"]["value"] < 0               # below the examiner ceiling
    assert rep["errors"]["omission"]["ai"]["precision"] < 1 and rep["errors"]["omission"]["ai"]["recall"] == 1


def test_rasch_recovers_a_planted_ai_severity(tmp_path):
    _, ai = write_dataset(tmp_path, students=40, segments=4, mus=4, ai_severity=0.35)
    ds = dataset.load("fil", tmp_path)
    mus = {(d, s): [1, 2, 3, 4] for d in ("d1", "d2") for s in range(1, 5)}
    obs = rasch.observations(ds, ai, mus, list(ds.recordings))
    f = rasch.fit(obs)
    assert f.raters["E1"][0] == pytest.approx(f.raters["E2"][0], abs=0.05)
    assert f.raters["AI"][0] - f.raters["E1"][0] > 0.5  # the AI marks MUs missed more often: positive severity
    files = rasch.export(obs, tmp_path / "rasch")
    assert all(p.exists() for p in files) and "Facets = 3" in files[1].read_text()


# ------------------------------------------------------------------ split, ledger, Label Studio


def test_split_is_by_student_frozen_and_tamper_evident(tmp_path):
    write_dataset(tmp_path)
    ds = dataset.load("fil", tmp_path)
    doc = split.freeze(ds, share=0.5)
    with pytest.raises(split.SplitError):
        split.freeze(ds)
    held, dev = split.recordings_for(ds, "heldout"), split.recordings_for(ds, "dev")
    students = lambda ids: {ds.recordings[i].student_id for i in ids}  # noqa: E731
    assert held and dev and not students(held) & students(dev) and set(held) == set(doc["held_out_recordings"])
    path = ds.root / "split.json"
    tampered = json.loads(path.read_text())
    tampered["held_out_recordings"] = tampered["held_out_recordings"][1:]
    path.write_text(json.dumps(tampered))
    with pytest.raises(split.SplitError, match="edited"):
        split.load(ds)


def test_label_studio_export_converts_to_annotations(tmp_path):
    export = [{"data": {"recording_id": "R1"}, "annotations": [
        {"completed_by": {"email": "anna@example.com"}, "result": [
            {"id": "a", "from_name": "error", "value": {"start": 1.234, "end": 2.5, "labels": ["omission"]}},
            {"id": "a", "from_name": "mu_no", "value": {"text": ["MU2"]}},
            {"id": "a", "from_name": "deduction", "value": {"text": ["1"]}},
            {"id": "b", "from_name": "error", "value": {"start": 6, "end": 7, "labels": ["indirect_speech"]}}]},
        {"completed_by": {"email": "ben@example.com"}, "result": [
            {"from_name": "no_errors", "value": {"choices": ["No errors in this answer"]}}]}]}]
    rows = label_studio.convert(export, {"anna@example.com": "E1", "ben@example.com": "E2"})
    assert rows[0] == {"recording_id": "R1", "examiner_id": "E1", "kind": "accuracy", "error_type": "omission",
                       "mu_no": "2", "start_s": 1.23, "end_s": 2.5, "deduction": "1", "quote": ""}
    assert rows[1]["kind"] == "language" and rows[1]["error_type"] == "indirect_speech"
    assert rows[2]["examiner_id"] == "E2" and rows[2]["kind"] == "none"
    label_studio.write_annotations(rows, tmp_path / "annotations.csv")
    assert label_studio.CONFIG_PATH.read_text().count("<Label ") == 14


# ------------------------------------------------------------------ gate


def test_gate_check_requires_a_passing_heldout_report_for_the_current_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "BASE_DIR", tmp_path / "backend")
    (tmp_path / "backend" / "config").mkdir(parents=True)
    monkeypatch.setattr(gate, "GATE_PATH", tmp_path / "backend" / "config" / "validated_languages.yaml")
    assert gate.check() == []  # nothing validated: nothing to check
    entry = {"report": "docs/validation/reports/fil-heldout.json"}
    assert "not committed" in gate.problems_for("fil", entry)[0]
    rep_path = tmp_path / entry["report"]
    rep_path.parent.mkdir(parents=True)
    fp = {"prompt": "evaluate_segment_v1", "scoring_yaml_sha": "old"}
    monkeypatch.setattr(gate, "current_fingerprint", lambda: {"prompt": "evaluate_segment_v1", "scoring_yaml_sha": "new"})
    rep_path.write_text(json.dumps({"split": "heldout", "bar": {"passed": True}, "run": fp}))
    assert gate.problems_for("fil", entry) == ["fil: validated with scoring_yaml_sha=old, the repo now has new; re-validate"]
    rep_path.write_text(json.dumps({"split": "dev", "bar": {"passed": False}, "run": {**fp, "scoring_yaml_sha": "new"}}))
    assert len(gate.problems_for("fil", entry)) == 2


def test_repository_gate_is_consistent():
    assert gate.check() == []


def test_bar_is_marked_proposed_until_agreed():
    bar = report.load_bar()
    assert bar["agreed_with_benchmark"] is False  # flip only with Benchmark's written agreement (and who/when)
    rep = {"dialogue_totals": {"units": 100, "icc_gap": {"value": 0.0}}, "quotes": {"share_in_transcript": 1.0},
           "timing": {"share_within_s": 1.0}, "pass_fail_test_63": {"fp": 1, "tn": 99, "false_pass_rate": 0.01}}
    result = report.evaluate_bar(rep, bar)
    assert all(c["passed"] for c in result["checks"]) and result["passed"] is False
