"""Agreement statistics for the scoring validation study. Pure functions over plain Python/numpy data, so each can be
checked against textbook examples (tests/test_validation_metrics.py).

Conventions
- A "rating" is a score given to one unit (a dialogue attempt, a two-dialogue test) by one rater (an examiner or "AI").
- Positive class for Pass/Fail statistics is Pass, because the costly mistake is the AI saying Pass when examiners
  say Fail (the student books the real exam too early): that is the false-pass rate.
- Confidence intervals are percentile bootstrap intervals that resample *students* (clusters), never single segments,
  because answers from the same student are not independent.
"""
from __future__ import annotations

import itertools
import math
import re
import unicodedata
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field

import numpy as np

# ------------------------------------------------------------------ reliability


def icc_a1(matrix: np.ndarray) -> float:
    """ICC(A,1): two-way random effects, absolute agreement, single rater (McGraw & Wong 1996, case 2A).

    matrix: n units x k raters, no missing values. Absolute agreement, not consistency: a rater who is always 5 marks
    harsher is penalised, which is what matters when the number itself is shown to students."""
    y = np.asarray(matrix, dtype=float)
    n, k = y.shape
    if n < 2 or k < 2:
        return math.nan
    grand = y.mean()
    rows, cols = y.mean(axis=1), y.mean(axis=0)
    msr = k * ((rows - grand) ** 2).sum() / (n - 1)
    msc = n * ((cols - grand) ** 2).sum() / (k - 1)
    resid = y - rows[:, None] - cols[None, :] + grand
    mse = (resid ** 2).sum() / ((n - 1) * (k - 1))
    denom = msr + (k - 1) * mse + k * (msc - mse) / n
    return float((msr - mse) / denom) if denom > 0 else math.nan


def quadratic_weighted_kappa(a: Sequence[int], b: Sequence[int], min_rating: int, max_rating: int) -> float:
    """Cohen's kappa with quadratic weights for two raters on an ordinal scale (e.g. integer dialogue marks 0-45)."""
    a, b = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
    if len(a) < 2:
        return math.nan
    m = max_rating - min_rating + 1
    observed = np.zeros((m, m))
    for x, y in zip(a - min_rating, b - min_rating, strict=True):
        observed[x, y] += 1
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / len(a)
    i, j = np.indices((m, m))
    w = (i - j) ** 2 / (m - 1) ** 2
    denom = (w * expected).sum()
    return float(1 - (w * observed).sum() / denom) if denom > 0 else math.nan


@dataclass
class Ratings:
    """unit -> rater -> score, plus unit -> student for cluster resampling."""
    scores: dict[Hashable, dict[str, float]]
    student_of: dict[Hashable, str]

    def raters(self) -> list[str]:
        return sorted({r for by in self.scores.values() for r in by})

    def examiners(self) -> list[str]:
        return [r for r in self.raters() if r != AI]

    def subset(self, units: Sequence[Hashable]) -> Ratings:
        # Duplicated units (from resampling) get distinct keys so they count twice.
        scores, student = {}, {}
        for i, u in enumerate(units):
            scores[(i, u)] = self.scores[u]
            student[(i, u)] = self.student_of[u]
        return Ratings(scores, student)

    def pair(self, r1: str, r2: str) -> tuple[np.ndarray, np.ndarray]:
        units = [u for u, by in self.scores.items() if r1 in by and r2 in by]
        return (np.array([self.scores[u][r1] for u in units], dtype=float),
                np.array([self.scores[u][r2] for u in units], dtype=float))

    def examiner_mean(self) -> dict[Hashable, float]:
        out = {}
        for u, by in self.scores.items():
            vals = [v for r, v in by.items() if r != AI]
            if vals:
                out[u] = float(np.mean(vals))
        return out


AI = "AI"


def pairwise_icc(r: Ratings, raters: Sequence[str]) -> float:
    """Mean ICC(A,1) over every pair of the given raters, each on the units both rated."""
    vals = []
    for r1, r2 in itertools.combinations(raters, 2):
        a, b = r.pair(r1, r2)
        if len(a) >= 2:
            vals.append(icc_a1(np.column_stack([a, b])))
    vals = [v for v in vals if not math.isnan(v)]
    return float(np.mean(vals)) if vals else math.nan


def examiner_ceiling_icc(r: Ratings) -> float:
    """How well examiners agree with each other: the most the AI can be expected to reach."""
    return pairwise_icc(r, r.examiners())


def ai_examiner_icc(r: Ratings) -> float:
    """Mean over examiners of ICC(A,1)(AI, that examiner): on the same footing as the examiner ceiling."""
    vals = []
    for e in r.examiners():
        a, b = r.pair(AI, e)
        if len(a) >= 2:
            vals.append(icc_a1(np.column_stack([a, b])))
    vals = [v for v in vals if not math.isnan(v)]
    return float(np.mean(vals)) if vals else math.nan


def ai_examiner_kappa(r: Ratings, max_rating: int) -> float:
    vals = []
    for e in r.examiners():
        a, b = r.pair(AI, e)
        if len(a) >= 2:
            vals.append(quadratic_weighted_kappa(np.rint(a), np.rint(b), 0, max_rating))
    vals = [v for v in vals if not math.isnan(v)]
    return float(np.mean(vals)) if vals else math.nan


def examiner_kappa(r: Ratings, max_rating: int) -> float:
    vals = []
    for r1, r2 in itertools.combinations(r.examiners(), 2):
        a, b = r.pair(r1, r2)
        if len(a) >= 2:
            vals.append(quadratic_weighted_kappa(np.rint(a), np.rint(b), 0, max_rating))
    vals = [v for v in vals if not math.isnan(v)]
    return float(np.mean(vals)) if vals else math.nan


def bland_altman(ai: Sequence[float], reference: Sequence[float]) -> dict:
    """AI minus reference (examiners' mean). Positive bias = the AI gives higher marks than examiners."""
    d = np.asarray(ai, dtype=float) - np.asarray(reference, dtype=float)
    if len(d) < 2:
        return {"n": len(d), "bias": math.nan, "sd": math.nan, "loa_low": math.nan, "loa_high": math.nan}
    bias, sd = float(d.mean()), float(d.std(ddof=1))
    return {"n": len(d), "bias": bias, "sd": sd, "loa_low": bias - 1.96 * sd, "loa_high": bias + 1.96 * sd}


# ------------------------------------------------------------------ pass / fail


def pass_fail(ai_pass: Sequence[bool], ref_pass: Sequence[bool]) -> dict:
    """Positive class = Pass. false_pass_rate = share of examiner-Fail units the AI passes (1 - specificity);
    false_pass_share = share of AI passes that examiners fail (what a student told "Pass" should worry about)."""
    a, r = np.asarray(ai_pass, dtype=bool), np.asarray(ref_pass, dtype=bool)
    tp, fp = int((a & r).sum()), int((a & ~r).sum())
    fn, tn = int((~a & r).sum()), int((~a & ~r).sum())
    div = lambda x, y: x / y if y else math.nan  # noqa: E731
    return {"n": len(a), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "sensitivity": div(tp, tp + fn), "specificity": div(tn, tn + fp),
            "false_pass_rate": div(fp, fp + tn), "false_pass_share": div(fp, fp + tp),
            "agreement": div(tp + tn, len(a))}


def calibration(ai: Sequence[float], reference: Sequence[float], ref_pass: Sequence[bool], width: float,
                maximum: float) -> list[dict]:
    """For each band of AI score: how many units, the examiners' mean score and how many examiners passed."""
    ai, ref, rp = np.asarray(ai, float), np.asarray(reference, float), np.asarray(ref_pass, bool)
    out = []
    lo = 0.0
    while lo < maximum + 1e-9:
        hi = lo + width
        m = (ai >= lo) & ((ai < hi) if hi <= maximum else (ai <= maximum))
        if m.any():
            out.append({"ai_from": lo, "ai_to": min(hi, maximum), "n": int(m.sum()),
                        "examiner_mean": float(ref[m].mean()), "examiner_pass_rate": float(rp[m].mean())})
        lo = hi
    return out


# ------------------------------------------------------------------ error-level matching


@dataclass(frozen=True)
class ErrorItem:
    """One identified error. mu_no for Meaning Unit errors (omission/distortion); times for everything else when
    known (examiner annotation, or the AI quote located in the speech-to-text word timings)."""
    recording_id: str
    type: str
    mu_no: int | None = None
    start: float | None = None
    end: float | None = None


MU_TYPES = ("omission", "distortion")


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: Counts) -> None:
        self.tp, self.fp, self.fn = self.tp + other.tp, self.fp + other.fp, self.fn + other.fn

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else math.nan

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else math.nan


def _overlaps(a: ErrorItem, b: ErrorItem, tolerance: float) -> bool:
    if a.start is None or b.start is None:
        return False
    a_end, b_end = a.end if a.end is not None else a.start, b.end if b.end is not None else b.start
    return a.start - tolerance <= b_end and b.start - tolerance <= a_end


def match_errors(predicted: list[ErrorItem], reference: list[ErrorItem], tolerance: float = 1.0
                 ) -> dict[str, Counts]:
    """One-to-one matching inside one recording, per error type.
    - omission/distortion: same Meaning Unit and same type.
    - everything else: same type and overlapping time (+/- tolerance seconds). Items with no time on either side are
      matched by count within the type (reported as such by the caller, since it is a weaker match)."""
    out: dict[str, Counts] = {}
    types = {i.type for i in predicted} | {i.type for i in reference}
    for t in types:
        p = [i for i in predicted if i.type == t]
        r = [i for i in reference if i.type == t]
        c = Counts()
        if t in MU_TYPES:
            pm, rm = {i.mu_no for i in p}, {i.mu_no for i in r}
            c.tp, c.fp, c.fn = len(pm & rm), len(pm - rm), len(rm - pm)
        else:
            unused = list(r)
            untimed_p = [i for i in p if i.start is None]
            for i in (i for i in p if i.start is not None):
                hit = next((j for j in unused if _overlaps(i, j, tolerance)), None)
                if hit is not None:
                    unused.remove(hit)
                    c.tp += 1
                else:
                    c.fp += 1
            # Untimed predictions can only pair with untimed reference items, by count.
            untimed_r = [j for j in unused if j.start is None]
            k = min(len(untimed_p), len(untimed_r))
            c.tp += k
            c.fp += len(untimed_p) - k
            c.fn += len(unused) - k
        out[t] = c
    return out


def mu_flag_counts(predicted: list[ErrorItem], reference: list[ErrorItem]) -> Counts:
    """Was the Meaning Unit penalised at all (omission or distortion), ignoring which of the two."""
    pm = {i.mu_no for i in predicted if i.type in MU_TYPES}
    rm = {i.mu_no for i in reference if i.type in MU_TYPES}
    return Counts(len(pm & rm), len(pm - rm), len(rm - pm))


# ------------------------------------------------------------------ speech-to-text and timing

_PUNCT = re.compile(r"[^\w\s'-]", re.UNICODE)


def normalise_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("P") or ch in "'-")
    return " ".join(_PUNCT.sub(" ", s).split())


def wer(references: Sequence[str], hypotheses: Sequence[str]) -> float:
    """Corpus word error rate (jiwer), after the same normalisation on both sides."""
    import jiwer
    pairs = [(normalise_text(r), normalise_text(h)) for r, h in zip(references, hypotheses, strict=True)]
    pairs = [(r, h) for r, h in pairs if r]
    if not pairs:
        return math.nan
    return float(jiwer.wer([r for r, _ in pairs], [h for _, h in pairs]))


@dataclass
class TimingComparison:
    start_errors: list[float] = field(default_factory=list)   # |AI speech start - human speech start|
    pause_counts: Counts = field(default_factory=Counts)
    pause_boundary_errors: list[float] = field(default_factory=list)


def compare_pauses(ai: list[tuple[float, float]], human: list[tuple[float, float]], tolerance: float = 0.5
                   ) -> tuple[Counts, list[float]]:
    """Pause events (start, end). A match overlaps within tolerance; boundary errors are |start diff| and |end diff|."""
    c, errors, unused = Counts(), [], list(human)
    for a in ai:
        hit = next((h for h in unused if a[0] - tolerance <= h[1] and h[0] - tolerance <= a[1]), None)
        if hit is None:
            c.fp += 1
            continue
        unused.remove(hit)
        c.tp += 1
        errors += [abs(a[0] - hit[0]), abs(a[1] - hit[1])]
    c.fn += len(unused)
    return c, errors


def quote_in_transcript(quote: str, transcript: str) -> bool:
    q = normalise_text(quote)
    return not q or q in normalise_text(transcript)


# ------------------------------------------------------------------ bootstrap


def cluster_bootstrap(units: Sequence[Hashable], cluster_of: Callable[[Hashable], str],
                      stat: Callable[[list[Hashable]], float], n_boot: int = 2000, seed: int = 20261030,
                      level: float = 0.95) -> tuple[float, float]:
    """Percentile CI of stat(units) resampling clusters (students) with replacement. NaN draws are dropped."""
    clusters: dict[str, list[Hashable]] = {}
    for u in units:
        clusters.setdefault(cluster_of(u), []).append(u)
    keys = sorted(clusters)
    if len(keys) < 2:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        sample = [u for i in pick for u in clusters[keys[i]]]
        v = stat(sample)
        if not (v is None or (isinstance(v, float) and math.isnan(v))):
            draws.append(v)
    if len(draws) < n_boot * 0.5:
        return math.nan, math.nan
    alpha = (1 - level) / 2
    return float(np.quantile(draws, alpha)), float(np.quantile(draws, 1 - alpha))
