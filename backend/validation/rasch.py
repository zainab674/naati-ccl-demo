"""Many-facet Rasch model of Meaning-Unit marking: student x rater x Meaning Unit.

    log-odds(MU conveyed) = ability(student) - difficulty(MU) - severity(rater)

Raters are the examiners plus "AI", so the AI's severity is measured on the examiners' scale: a positive AI severity
means the AI marks Meaning Units as missed more often than the examiners do for the same students. MU difficulties
summed per dialogue show how much harder a dialogue is because of how it was split, which is the Meaning-Unit-count
problem measured on real marking rather than simulated.

Fitted here by penalised joint maximum likelihood (a small ridge keeps students with all-correct or all-wrong answers
finite; facets are centred so mean MU difficulty and mean rater severity are 0). For a published analysis, re-fit with
FACETS (Linacre) or R TAM's tam.mml.mfr from the exported files: JML estimates are slightly spread out.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from .ai_runs import AIRecording
from .dataset import Dataset
from .metrics import AI, MU_TYPES

RIDGE = 0.01


@dataclass
class Obs:
    student: str
    rater: str
    item: tuple[str, int, int]  # (dialogue_key, segment_no, mu_no)
    x: int                      # 1 = conveyed, 0 = omission/distortion


def observations(ds: Dataset, ai: dict[str, AIRecording], mus: dict[tuple[str, int], list[int]],
                 recording_ids: list[str]) -> list[Obs]:
    """mus: (dialogue_key, segment_no) -> active MU numbers (from the database)."""
    out = []
    for rid in recording_ids:
        rec = ds.recordings[rid]
        numbers = mus.get((rec.dialogue_key, rec.segment_no), [])
        raters: dict[str, set[int]] = {}
        for e in ds.reviewed_by(rid):
            raters[e] = {i.mu_no for i in ds.errors(rid, e) if i.type in MU_TYPES}
        if rid in ai and not ai[rid].error:
            raters[AI] = {i.mu_no for i in ai[rid].items if i.type in MU_TYPES}
        for rater, missed in raters.items():
            for n in numbers:
                out.append(Obs(rec.student_id, rater, (rec.dialogue_key, rec.segment_no, n), 0 if n in missed else 1))
    return out


@dataclass
class Fit:
    students: dict[str, tuple[float, float]]           # measure, standard error
    raters: dict[str, tuple[float, float, float, float]]  # measure, SE, infit MnSq, outfit MnSq
    items: dict[tuple[str, int, int], tuple[float, float]]
    dialogues: dict[str, dict]                          # dialogue_key -> MU count, expected misses at ability 0
    n_obs: int


def fit(obs: list[Obs]) -> Fit:
    if not obs:
        raise ValueError("No Meaning Unit observations (need examiner marks and the dialogues' MUs)")
    s_ids = sorted({o.student for o in obs})
    r_ids = sorted({o.rater for o in obs})
    i_ids = sorted({o.item for o in obs})
    si = np.array([s_ids.index(o.student) for o in obs])
    ri = np.array([r_ids.index(o.rater) for o in obs])
    ii = np.array([i_ids.index(o.item) for o in obs])
    x = np.array([o.x for o in obs], dtype=float)
    ns, nr, ni = len(s_ids), len(r_ids), len(i_ids)

    def unpack(v):
        return v[:ns], v[ns:ns + nr], v[ns + nr:]

    def nll(v):
        th, lam, de = unpack(v)
        eta = th[si] - de[ii] - lam[ri]
        p = 1 / (1 + np.exp(-eta))
        ll = (x * eta - np.logaddexp(0, eta)).sum() - RIDGE * (v ** 2).sum()
        resid = x - p
        g_th = np.bincount(si, resid, ns)
        g_lam = -np.bincount(ri, resid, nr)
        g_de = -np.bincount(ii, resid, ni)
        return -ll, -(np.concatenate([g_th, g_lam, g_de]) - 2 * RIDGE * v)

    res = minimize(nll, np.zeros(ns + nr + ni), jac=True, method="L-BFGS-B")
    th, lam, de = unpack(res.x)
    shift_i, shift_r = de.mean(), lam.mean()  # centre facets; the ability scale absorbs the shift
    de, lam, th = de - shift_i, lam - shift_r, th - shift_i - shift_r
    eta = th[si] - de[ii] - lam[ri]
    p = 1 / (1 + np.exp(-eta))
    info = p * (1 - p)
    z2 = (x - p) ** 2 / np.maximum(info, 1e-9)

    def se(idx, n):
        return 1 / np.sqrt(np.maximum(np.bincount(idx, info, n), 1e-9))

    def infit(idx, n):
        return np.bincount(idx, (x - p) ** 2, n) / np.maximum(np.bincount(idx, info, n), 1e-9)

    def outfit(idx, n):
        return np.bincount(idx, z2, n) / np.maximum(np.bincount(idx, minlength=n), 1)

    se_s, se_r, se_i = se(si, ns), se(ri, nr), se(ii, ni)
    inf_r, out_r = infit(ri, nr), outfit(ri, nr)
    items = {i_ids[k]: (float(de[k]), float(se_i[k])) for k in range(ni)}
    dialogues: dict[str, dict] = defaultdict(lambda: {"meaning_units": 0, "expected_misses_average_student": 0.0})
    for (dkey, _seg, _mu), (d, _) in items.items():
        dialogues[dkey]["meaning_units"] += 1
        dialogues[dkey]["expected_misses_average_student"] += float(1 / (1 + np.exp(-d)))  # P(miss) at ability 0
    return Fit({s_ids[k]: (float(th[k]), float(se_s[k])) for k in range(ns)},
               {r_ids[k]: (float(lam[k]), float(se_r[k]), float(inf_r[k]), float(out_r[k])) for k in range(nr)},
               items, dict(dialogues), len(obs))


def to_markdown(f: Fit) -> str:
    lines = [f"Observations: {f.n_obs} (student x rater x Meaning Unit).", "",
             "| rater | severity (logits) | SE | infit MnSq | outfit MnSq |", "|---|---|---|---|---|"]
    for r, (m, se, inf, out) in sorted(f.raters.items(), key=lambda kv: kv[1][0]):
        lines.append(f"| {r} | {m:+.2f} | {se:.2f} | {inf:.2f} | {out:.2f} |")
    lines += ["", "Positive severity = marks Meaning Units as missed more often. Mean square fit 0.5-1.5 is usually "
              "taken as productive for measurement.", "",
              "| dialogue | Meaning Units | expected misses, average student |", "|---|---|---|"]
    for d, v in sorted(f.dialogues.items()):
        lines.append(f"| {d} | {v['meaning_units']} | {v['expected_misses_average_student']:.1f} |")
    lines += ["", "Expected misses grow with the number of Meaning Units: under -1 per MU that is the dialogue's "
              "built-in penalty for the same student."]
    return "\n".join(lines)


def export(obs: list[Obs], out_dir: Path) -> list[Path]:
    """FACETS data/spec and a long CSV + R TAM script, for an independent re-fit."""
    out_dir.mkdir(parents=True, exist_ok=True)
    s_ids = sorted({o.student for o in obs})
    r_ids = sorted({o.rater for o in obs})
    i_ids = sorted({o.item for o in obs})
    long_csv = out_dir / "mu_observations.csv"
    with long_csv.open("w", encoding="utf-8") as f:
        f.write("student,rater,item,x\n")
        for o in obs:
            f.write(f"{o.student},{o.rater},{o.item[0]}|{o.item[1]}|{o.item[2]},{o.x}\n")
    spec = out_dir / "facets_spec.txt"
    lines = ["Title = CCL Meaning Unit marking", "Facets = 3", "Positive = 1", "Noncenter = 1", "Models = ?,?,?,D",
             "Labels =", "1,Student"]
    lines += [f"{k + 1}={s}" for k, s in enumerate(s_ids)] + ["*", "2,Rater"]
    lines += [f"{k + 1}={r}" for k, r in enumerate(r_ids)] + ["*", "3,MeaningUnit"]
    lines += [f"{k + 1}={i[0]} s{i[1]} mu{i[2]}" for k, i in enumerate(i_ids)] + ["*", "Data ="]
    lines += [f"{s_ids.index(o.student) + 1},{r_ids.index(o.rater) + 1},{i_ids.index(o.item) + 1},{o.x}" for o in obs]
    spec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r_script = out_dir / "fit_tam.R"
    r_script.write_text(
        "# Many-facet Rasch re-fit with TAM (install.packages('TAM')).\n"
        "library(TAM)\nd <- read.csv('mu_observations.csv')\n"
        "wide <- reshape(d[, c('student','rater','item','x')], idvar = c('student','rater'), timevar = 'item',"
        " direction = 'wide')\n"
        "resp <- wide[, grep('^x\\\\.', names(wide))]\n"
        "facets <- data.frame(rater = wide$rater)\n"
        "mod <- tam.mml.mfr(resp = resp, facets = facets, formulaA = ~ item + rater, pid = wide$student)\n"
        "summary(mod)\nprint(mod$xsi.facets)\n", encoding="utf-8")
    return [long_csv, spec, r_script]
