"""How the number of Meaning Units a dialogue is split into changes a student's dialogue score, with and without the
accuracy_normalisation adjustment. A model, not data: students convey each MU independently with probability p and make
Poisson(lam) other errors per segment at 0.5 each, scored by the production engine. It shows the size of the rubric
effect; the Rasch analysis on examiner data is what measures it for real.

    python -m validation simulate
"""
from __future__ import annotations

import copy

import numpy as np

from app.services.scoring import engine
from app.settings import scoring_config

SCENARIOS = [  # (segments, MUs per segment, share of MUs conveyed, other errors per segment)
    (12, 3, 0.85, 1.0), (14, 4, 0.85, 1.0), (16, 5, 0.85, 1.0),
    (12, 3, 0.70, 1.0), (14, 4, 0.70, 1.0), (16, 5, 0.70, 1.0),
]


def simulate(segments: int, mus: int, p: float, lam: float, normalise: bool, n: int = 20000, seed: int = 7) -> dict:
    cfg = copy.deepcopy(scoring_config())
    cfg.setdefault("accuracy_normalisation", {"reference_meaning_units": 40})
    cfg["accuracy_normalisation"]["enabled"] = normalise
    rng = np.random.default_rng(seed)
    total_mus = segments * mus
    missed = rng.binomial(total_mus, 1 - p, n)
    other = rng.poisson(lam * segments, n)
    scores = np.array([engine.dialogue_score([engine.Totals(float(a), 0.5 * float(b), 0.0)], 45, 29, cfg,
                                             meaning_units=total_mus).score for a, b in zip(missed, other, strict=True)])
    return {"segments": segments, "mus": total_mus, "p_conveyed": p, "other_per_segment": lam,
            "normalised": normalise, "mean": float(scores.mean()), "p_zero": float((scores <= 0).mean()),
            "p_pass_29": float((scores >= 29).mean())}


def table() -> list[dict]:
    return [simulate(s, m, p, lam, norm) for s, m, p, lam in SCENARIOS for norm in (False, True)]


def to_markdown(rows: list[dict]) -> str:
    ref = scoring_config().get("accuracy_normalisation", {}).get("reference_meaning_units", 40)
    lines = [f"| MUs in dialogue | MUs conveyed | other errors / segment | adjustment (ref {ref}) | mean /45 | P(score 0) | P(>= 29) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['segments']} x {r['mus'] // r['segments']} = {r['mus']} | {r['p_conveyed']:.0%} | "
                     f"{r['other_per_segment']:g} | {'on' if r['normalised'] else 'off'} | {r['mean']:.1f} | "
                     f"{r['p_zero']:.2f} | {r['p_pass_29']:.2f} |")
    return "\n".join(lines)
