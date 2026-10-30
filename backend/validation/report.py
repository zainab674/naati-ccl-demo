"""Builds the validation report for one language and one split from the dataset and the AI results.

Three scores per dialogue keep the two sources of disagreement apart:
- examiner mark:   what the examiner gave (dialogue_marks.csv, else 45 minus their own deductions)
- examiner+brief:  the Scoring Brief's fixed penalties applied to the errors the examiner found
- AI:              the platform (AI-identified errors, brief penalties)
examiner mark vs examiner+brief measures the rubric (are fixed -1/-0.5 penalties how examiners mark?);
examiner+brief vs AI measures error identification. A low AI-vs-examiner ICC can come from either.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import yaml

from app.services.scoring import engine
from app.settings import BASE_DIR, scoring_config

from . import metrics as m
from .ai_runs import ENGINE_TYPE, AIRecording, engine_item
from .dataset import NOT_DETECTED_BY_AI, Dataset

BAR_PATH = BASE_DIR / "validation" / "bar.yaml"


def load_bar() -> dict:
    return yaml.safe_load(BAR_PATH.read_text(encoding="utf-8"))


def _brief_deduction(error_type: str) -> float | None:
    if error_type not in ENGINE_TYPE:
        return None
    return engine.item_deduction(engine_item(error_type), scoring_config()).deduction


@dataclass
class Units:
    """Dialogue attempts (test_id, dialogue_key) whose recordings are all in the split and scored by the AI."""
    keys: list[tuple[str, str]]
    marked: m.Ratings     # examiners' own marks + AI
    brief: m.Ratings      # examiners' errors under brief penalties (raters prefixed "brief:")
    excluded: list[str]


def dialogue_units(ds: Dataset, ai: dict[str, AIRecording], recording_ids: set[str]) -> Units:
    cfg = scoring_config()
    maximum, passing = float(cfg["dialogue_max"]), float(cfg["pass_min_per_dialogue"])
    marked, brief, student, keys, excluded = {}, {}, {}, [], []
    for unit, rids in ds.dialogue_units().items():
        if not set(rids) <= recording_ids:
            continue
        failed = [r for r in rids if ai.get(r) is None or ai[r].error]
        if failed:
            excluded.append(f"{unit[0]}/{unit[1]}: AI scoring failed for {', '.join(failed)}")
            continue
        segs = [engine.Totals(**ai[r].deductions) for r in rids]
        mus = sum(ai[r].mu_count for r in rids) or None
        marked[unit] = {m.AI: engine.dialogue_score(segs, maximum, passing, cfg, meaning_units=mus).score}
        brief[unit] = {}
        given = ds.dialogue_marks.get(unit, {})
        for e in ds.examiners():
            if not all(e in ds.reviewed_by(r) for r in rids):
                continue
            own, rule = 0.0, engine.Totals()
            for r in rids:
                for a in (x for x in ds.annotations.get(r, []) if x.examiner_id == e and x.item):
                    b = _brief_deduction(a.item.type)
                    own += a.deduction if a.deduction is not None else (b or 0.0)
                    if b:
                        crit = ENGINE_TYPE[a.item.type][0]
                        setattr(rule, crit, getattr(rule, crit) + b)
            marked[unit][e] = given.get(e, max(0.0, maximum - own))
            brief[unit][f"brief:{e}"] = engine.dialogue_score([rule], maximum, passing, cfg, meaning_units=mus).score
        for e, score in given.items():  # a dialogue mark without segment annotations still counts as a mark
            marked[unit].setdefault(e, score)
        student[unit] = ds.student_of_unit(unit)
        keys.append(unit)
    return Units(keys, m.Ratings(marked, student), m.Ratings(brief, student), excluded)


def _ci(units, student_of, fn, n_boot):
    lo, hi = m.cluster_bootstrap(units, student_of, fn, n_boot=n_boot)
    return [lo, hi]


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)


def build(ds: Dataset, ai: dict[str, AIRecording], recording_ids: list[str], split: str, run: dict,
          n_boot: int = 2000) -> dict:
    cfg, bar = scoring_config(), load_bar()
    rset = set(recording_ids)
    u = dialogue_units(ds, ai, rset)
    keys, r = u.keys, u.marked
    st = r.student_of
    max45, pass29, pass63 = int(cfg["dialogue_max"]), float(cfg["pass_min_per_dialogue"]), float(cfg["pass_total"])

    def sub(units):
        return r.subset(units)

    # --- dialogue totals: reliability and agreement
    ceiling = m.examiner_ceiling_icc(r)
    ai_icc = m.ai_examiner_icc(r)
    ex_mean = r.examiner_mean()
    with_ex = [k for k in keys if k in ex_mean]
    totals = {
        "units": len(keys), "students": len({st[k] for k in keys}), "examiners": r.examiners(),
        "examiner_vs_examiner_icc": {"value": _num(ceiling), "ci95": _ci(keys, st.get, lambda s: m.examiner_ceiling_icc(sub(s)), n_boot)},
        "ai_vs_examiner_icc": {"value": _num(ai_icc), "ci95": _ci(keys, st.get, lambda s: m.ai_examiner_icc(sub(s)), n_boot)},
        "icc_gap": {"value": _num(ai_icc - ceiling),
                    "ci95": _ci(keys, st.get, lambda s: m.ai_examiner_icc(sub(s)) - m.examiner_ceiling_icc(sub(s)), n_boot)},
        "examiner_vs_examiner_kappa_qw": _num(m.examiner_kappa(r, max45)),
        "ai_vs_examiner_kappa_qw": _num(m.ai_examiner_kappa(r, max45)),
        "bland_altman": {k: _num(v) for k, v in m.bland_altman([r.scores[k][m.AI] for k in with_ex],
                                                                [ex_mean[k] for k in with_ex]).items()},
    }
    # Rubric fidelity: each examiner's own marks vs the brief's penalties on that examiner's errors.
    fid = []
    for e in r.examiners():
        pairs = [(r.scores[k][e], u.brief.scores[k][f"brief:{e}"]) for k in keys
                 if e in r.scores[k] and f"brief:{e}" in u.brief.scores.get(k, {})]
        if len(pairs) >= 2:
            fid.append({"examiner": e, "n": len(pairs), "icc": _num(m.icc_a1(np.array(pairs))),
                        "mean_diff_brief_minus_mark": _num(np.mean([b - a for a, b in pairs]))})
    totals["rubric_fidelity"] = fid

    # --- pass/fail per dialogue (29) and per two-dialogue test (63 and 29 each)
    ref_pass = [ex_mean[k] >= pass29 for k in with_ex]
    ai_scores = [r.scores[k][m.AI] for k in with_ex]
    dialogue_pf = m.pass_fail([s >= pass29 for s in ai_scores], ref_pass)
    dialogue_pf["calibration"] = m.calibration(ai_scores, [ex_mean[k] for k in with_ex], ref_pass, 5, max45)
    tests = defaultdict(list)
    for k in with_ex:
        tests[k[0]].append(k)
    test_ai, test_ref, test_ai_pass, test_ref_pass, test_student = [], [], [], [], []
    for ks in tests.values():
        if len(ks) != 2:
            continue
        a = [r.scores[k][m.AI] for k in ks]
        e = [ex_mean[k] for k in ks]
        test_ai.append(sum(a))
        test_ref.append(sum(e))
        test_ai_pass.append(sum(a) >= pass63 and min(a) >= pass29)
        test_ref_pass.append(sum(e) >= pass63 and min(e) >= pass29)
        test_student.append(st[ks[0]])
    test_pf = m.pass_fail(test_ai_pass, test_ref_pass)
    test_pf["calibration"] = m.calibration(test_ai, test_ref, test_ref_pass, 10, 2 * max45)
    idx = list(range(len(test_ai)))
    test_pf["false_pass_rate_ci95"] = _ci(idx, lambda i: test_student[i], lambda s: m.pass_fail(
        [test_ai_pass[i] for i in s], [test_ref_pass[i] for i in s])["false_pass_rate"], n_boot)

    # --- error identification: AI vs each examiner, and examiner vs examiner (ceiling)
    per_rec_ai: dict[str, dict[str, m.Counts]] = {}
    ai_by_type, ceil_by_type = defaultdict(m.Counts), defaultdict(m.Counts)
    mu_ai, mu_ceil = m.Counts(), m.Counts()
    tol = float(bar["error_match_tolerance_s"])
    for rid in sorted(rset):
        rec = ai.get(rid)
        if rec is None or rec.error:
            continue
        examiners = sorted(ds.reviewed_by(rid))
        per_rec_ai[rid] = defaultdict(m.Counts)
        for e in examiners:
            ref = ds.errors(rid, e)
            for t, c in m.match_errors(rec.error_items(), ref, tol).items():
                ai_by_type[t].add(c)
                per_rec_ai[rid][t].add(c)
            mu_ai.add(m.mu_flag_counts(rec.error_items(), ref))
        for e1, e2 in ((a, b) for i, a in enumerate(examiners) for b in examiners[i + 1:]):
            for t, c in m.match_errors(ds.errors(rid, e1), ds.errors(rid, e2), tol).items():
                ceil_by_type[t].add(c)
            mu_ceil.add(m.mu_flag_counts(ds.errors(rid, e1), ds.errors(rid, e2)))
    rec_student = {rid: ds.recordings[rid].student_id for rid in per_rec_ai}

    def pr_ci(t, attr):
        def stat(sample):
            c = m.Counts()
            for rid in sample:
                c.add(per_rec_ai[rid].get(t, m.Counts()))
            return getattr(c, attr)
        return _ci(list(per_rec_ai), rec_student.get, stat, n_boot)

    errors = {}
    for t in sorted(set(ai_by_type) | set(ceil_by_type)):
        c, cc = ai_by_type[t], ceil_by_type[t]
        errors[t] = {"ai": {"tp": c.tp, "fp": c.fp, "fn": c.fn, "precision": _num(c.precision),
                            "recall": _num(c.recall), "precision_ci95": pr_ci(t, "precision"),
                            "recall_ci95": pr_ci(t, "recall")},
                     "examiner_vs_examiner": {"precision": _num(cc.precision), "recall": _num(cc.recall)},
                     "not_detectable_by_ai": t in NOT_DETECTED_BY_AI}
    errors["_meaning_unit_flagged"] = {"ai": {"precision": _num(mu_ai.precision), "recall": _num(mu_ai.recall)},
                                       "examiner_vs_examiner": {"precision": _num(mu_ceil.precision),
                                                                "recall": _num(mu_ceil.recall)}}

    # --- speech-to-text
    stt_ids = [rid for rid in rset if rid in ds.transcripts and rid in ai and not ai[rid].error]

    def wer_of(ids):
        return m.wer([ds.transcripts[i][0] for i in ids], [ai[i].transcript for i in ids])
    rs = lambda i: ds.recordings[i].student_id  # noqa: E731
    mixed = [i for i in stt_ids if ds.transcripts[i][1]]
    plain = [i for i in stt_ids if not ds.transcripts[i][1]]
    stt = {"n": len(stt_ids), "wer": _num(wer_of(stt_ids)) if stt_ids else None,
           "wer_ci95": _ci(stt_ids, rs, wer_of, n_boot) if stt_ids else None,
           "mixed_language": {"n": len(mixed), "wer": _num(wer_of(mixed)) if mixed else None},
           "single_language": {"n": len(plain), "wer": _num(wer_of(plain)) if plain else None}}

    # --- timing
    within = float(bar["timing_within_s"])
    t_ids = [rid for rid in rset if rid in ds.timings and rid in ai and not ai[rid].error]
    start_err, pause_c, bounds = [], m.Counts(), []
    for rid in t_ids:
        hs, hp = ds.timings[rid]
        if hs is not None and ai[rid].speech_start is not None:
            start_err.append(abs(ai[rid].speech_start - hs))
        c, b = m.compare_pauses(ai[rid].pauses, hp, within)
        pause_c.add(c)
        bounds += b
    all_t = start_err + bounds
    timing = {"n": len(t_ids), "speech_start_mean_abs_error_s": _num(np.mean(start_err)) if start_err else None,
              "pause_precision": _num(pause_c.precision), "pause_recall": _num(pause_c.recall),
              "pause_boundary_mean_abs_error_s": _num(np.mean(bounds)) if bounds else None,
              "share_within_s": _num(np.mean([x <= within for x in all_t])) if all_t else None}

    # --- quotes
    quoted = [i for rid in rset if rid in ai for i in ai[rid].items if i.source == "evaluator" and i.quote]
    quotes = {"n": len(quoted), "share_in_transcript": _num(np.mean([i.quote_ok for i in quoted])) if quoted else None}

    # --- real exam outcomes (predictive validity)
    # A student's real result is compared with their AI test score (test_* lists share one order: tests with 2
    # dialogues). With several platform tests per student each is compared with the same real result.
    exam = []
    for i, stud in enumerate(test_student):
        if stud in ds.exam_results:
            res = ds.exam_results[stud]
            exam.append((test_ai_pass[i], res["result"].strip().lower() == "pass", test_ai[i], float(res["total"] or 0)))
    predictive = {"n": len(exam)}
    if exam:
        predictive.update(m.pass_fail([a for a, _, _, _ in exam], [b for _, b, _, _ in exam]))
        if len(exam) >= 3:
            predictive["pearson_ai_total_vs_exam_total"] = _num(np.corrcoef([c for *_, c, _ in exam],
                                                                             [d for *_, d in exam])[0, 1])

    report = {"language": ds.language, "split": split, "run": run, "recordings": len(rset),
              "excluded": u.excluded + ds.problems, "dialogue_totals": totals, "pass_fail_dialogue_29": dialogue_pf,
              "pass_fail_test_63": test_pf, "errors": errors, "speech_to_text": stt, "timing": timing,
              "quotes": quotes, "exam_outcomes": predictive}
    report["bar"] = evaluate_bar(report, bar)
    return report


def evaluate_bar(report: dict, bar: dict) -> dict:
    """Each check: passed True/False, or None when there is not enough data to judge (which is not a pass)."""
    t, pf = report["dialogue_totals"], report["pass_fail_test_63"]
    checks = []

    def add(name, value, ok, need):
        checks.append({"check": name, "value": value, "passed": ok, "requirement": need})

    n_units, n_fail = t["units"], pf["fp"] + pf["tn"]
    add("enough dialogue attempts", n_units, n_units >= bar["min_dialogue_units"], f">= {bar['min_dialogue_units']}")
    add("enough examiner-failed tests", n_fail, n_fail >= bar["min_failed_tests"], f">= {bar['min_failed_tests']}")
    gap = t["icc_gap"]["value"]
    add("AI-vs-examiner ICC within margin of the examiner ceiling", gap,
        None if gap is None else gap >= -bar["icc_margin"], f">= -{bar['icc_margin']}")
    fpr = pf["false_pass_rate"]
    add("false-pass rate at 63", _num(fpr), None if fpr is None or math.isnan(fpr) else fpr <= bar["false_pass_rate_max"],
        f"<= {bar['false_pass_rate_max']}")
    q = report["quotes"]["share_in_transcript"]
    add("AI quotes found in the transcript", q, None if q is None else q >= bar["quote_share_min"],
        f">= {bar['quote_share_min']}")
    w = report["timing"]["share_within_s"]
    add(f"timing within {bar['timing_within_s']} s of hand-marked", w,
        None if w is None else w >= bar["timing_within_share_min"], f">= {bar['timing_within_share_min']}")
    passed = all(c["passed"] is True for c in checks)
    return {"agreed_with_benchmark": bool(bar.get("agreed_with_benchmark")), "checks": checks,
            "passed": passed and bool(bar.get("agreed_with_benchmark"))}


def to_markdown(rep: dict) -> str:
    t, b = rep["dialogue_totals"], rep["bar"]
    fmt = lambda v: "n/a" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))  # noqa: E731
    ci = lambda c: "" if not c or c[0] is None or (isinstance(c[0], float) and math.isnan(c[0])) else f" ({c[0]:.3f} to {c[1]:.3f})"  # noqa: E731
    lines = [f"# Scoring validation: {rep['language']} ({rep['split']})", "",
             f"Run: `{rep['run'].get('key', '')}` prompt {rep['run'].get('prompt')} / evaluator {rep['run'].get('evaluator')} "
             f"/ STT {rep['run'].get('stt_model')} / commit {rep['run'].get('commit')}", "",
             f"Recordings {rep['recordings']}, dialogue attempts {t['units']}, students {t['students']}, "
             f"examiners {', '.join(t['examiners']) or 'none'}.", "",
             "## Bar" + ("" if b["agreed_with_benchmark"] else " (PROPOSED: not yet agreed with Benchmark)"), "",
             "| check | value | requirement | result |", "|---|---|---|---|"]
    for c in b["checks"]:
        res = {True: "pass", False: "FAIL", None: "not enough data"}[c["passed"]]
        lines.append(f"| {c['check']} | {fmt(c['value'])} | {c['requirement']} | {res} |")
    lines += ["", f"**Overall: {'PASSED' if b['passed'] else 'NOT PASSED'}**", "", "## Dialogue totals (/45)", "",
              f"- Examiner vs examiner ICC(A,1): {fmt(t['examiner_vs_examiner_icc']['value'])}{ci(t['examiner_vs_examiner_icc']['ci95'])}",
              f"- AI vs examiner ICC(A,1): {fmt(t['ai_vs_examiner_icc']['value'])}{ci(t['ai_vs_examiner_icc']['ci95'])}",
              f"- Gap (AI - ceiling): {fmt(t['icc_gap']['value'])}{ci(t['icc_gap']['ci95'])}",
              f"- Quadratic weighted kappa: examiners {fmt(t['examiner_vs_examiner_kappa_qw'])}, AI {fmt(t['ai_vs_examiner_kappa_qw'])}",
              f"- Bland-Altman (AI - examiner mean): bias {fmt(t['bland_altman']['bias'])}, limits "
              f"{fmt(t['bland_altman']['loa_low'])} to {fmt(t['bland_altman']['loa_high'])}", ""]
    for f in t["rubric_fidelity"]:
        lines.append(f"- Rubric fidelity, {f['examiner']}: ICC(own mark, brief penalties on own errors) {fmt(f['icc'])}, "
                     f"brief minus mark {fmt(f['mean_diff_brief_minus_mark'])} (n={f['n']})")
    for name, key in (("Pass/Fail per dialogue (29)", "pass_fail_dialogue_29"), ("Pass/Fail per test (63, 29 each)", "pass_fail_test_63")):
        p = rep[key]
        lines += ["", f"## {name}", "", f"n {p['n']}: sensitivity {fmt(p['sensitivity'])}, specificity {fmt(p['specificity'])}, "
                  f"false-pass rate {fmt(p['false_pass_rate'])}{ci(p.get('false_pass_rate_ci95'))}, "
                  f"share of AI passes that examiners fail {fmt(p['false_pass_share'])}", "",
                  "| AI score | n | examiner mean | examiner pass rate |", "|---|---|---|---|"]
        lines += [f"| {c['ai_from']:g}-{c['ai_to']:g} | {c['n']} | {c['examiner_mean']:.1f} | {c['examiner_pass_rate']:.2f} |"
                  for c in p["calibration"]]
    lines += ["", "## Errors (AI vs each examiner; examiner vs examiner is the ceiling)", "",
              "| type | AI precision | AI recall | examiners precision | examiners recall | note |", "|---|---|---|---|---|---|"]
    for typ, e in rep["errors"].items():
        note = "AI cannot report this type" if e.get("not_detectable_by_ai") else ""
        lines.append(f"| {typ} | {fmt(e['ai']['precision'])}{ci(e['ai'].get('precision_ci95'))} | "
                     f"{fmt(e['ai']['recall'])}{ci(e['ai'].get('recall_ci95'))} | {fmt(e['examiner_vs_examiner']['precision'])} | "
                     f"{fmt(e['examiner_vs_examiner']['recall'])} | {note} |")
    s, tm, q, ex = rep["speech_to_text"], rep["timing"], rep["quotes"], rep["exam_outcomes"]
    lines += ["", "## Speech-to-text, timing, quotes, real exams", "",
              f"- WER {fmt(s['wer'])}{ci(s.get('wer_ci95'))} (n={s['n']}); mixed-language {fmt(s['mixed_language']['wer'])} "
              f"(n={s['mixed_language']['n']}); single-language {fmt(s['single_language']['wer'])} (n={s['single_language']['n']})",
              f"- Timing (n={tm['n']}): speech start error {fmt(tm['speech_start_mean_abs_error_s'])} s, pause precision "
              f"{fmt(tm['pause_precision'])}, recall {fmt(tm['pause_recall'])}, share within bar {fmt(tm['share_within_s'])}",
              f"- AI quotes found in the transcript: {fmt(q['share_in_transcript'])} (n={q['n']})",
              f"- Real NAATI results: n={ex['n']}" + (f", AI Pass vs real Pass agreement {fmt(ex.get('agreement'))}, "
                                                       f"false-pass rate {fmt(ex.get('false_pass_rate'))}" if ex["n"] else ""), ""]
    if rep["excluded"]:
        lines += ["## Excluded or problems", ""] + [f"- {x}" for x in rep["excluded"][:50]] + [""]
    return "\n".join(lines)
