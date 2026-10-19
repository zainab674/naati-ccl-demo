"""Deduction engine: pure functions, no database, no AI. Every number comes from config/scoring.yaml.

    Accuracy & Completeness : omission / distortion x MU weight, insertion  (default -1 each)
    Language Quality        : per occurrence (default -0.5); pronunciation is review-only unless switched on
    Fluency                 : per occurrence (default -0.5); pauses and start delays come from audio analysis
An admin override replaces the computed deduction of one item. Scores are floored at 0.
"""
from dataclasses import dataclass, field

ACCURACY_KEYS = {"Omission": "omission", "Distortion": "distortion", "Insertion": "insertion", "Correct": None}
LANGUAGE_KEYS = {"Grammar": "grammar", "UnidiomaticUsage": "unidiomatic_usage", "Register": "register",
                 "SentenceStructure": "sentence_structure", "Pronunciation": "pronunciation"}
FLUENCY_KEYS = {"Pause": "pause", "StartDelay": "start_delay", "Hesitation": "hesitation",
                "SelfCorrection": "self_correction"}


@dataclass
class Item:
    criterion: str                # "accuracy" | "language" | "fluency"
    type: str                     # enum value, e.g. "Omission", "Grammar", "Pause"
    weight: float = 1.0           # Meaning Unit weight (accuracy only)
    override: float | None = None  # admin-revised deduction


@dataclass
class ItemResult:
    deduction: float
    needs_review: bool = False


@dataclass
class Totals:
    accuracy: float = 0.0
    language: float = 0.0
    fluency: float = 0.0

    @property
    def total(self) -> float:
        return round(self.accuracy + self.language + self.fluency, 2)

    def add(self, other: "Totals") -> "Totals":
        return Totals(round(self.accuracy + other.accuracy, 2), round(self.language + other.language, 2),
                      round(self.fluency + other.fluency, 2))


@dataclass
class DialogueScore:
    deductions: Totals
    score: float
    maximum: float
    passing: float

    @property
    def passed(self) -> bool:
        return self.score >= self.passing


@dataclass
class MockScore:
    total: float
    maximum: float
    passed: bool
    reasons: list[str] = field(default_factory=list)


def item_deduction(item: Item, cfg: dict) -> ItemResult:
    p = cfg["penalties"]
    if item.criterion == "accuracy":
        key = ACCURACY_KEYS.get(item.type)
        if key is None:
            value = 0.0
        else:
            value = float(p["accuracy_completeness"][key])
            if key != "insertion" and p["accuracy_completeness"].get("use_meaning_unit_weight", True):
                value *= item.weight
        result = ItemResult(value)
    elif item.criterion == "language":
        key = LANGUAGE_KEYS[item.type]
        if key == "pronunciation" and not cfg.get("pronunciation_auto_deduct", False):
            result = ItemResult(0.0, needs_review=True)
        else:
            result = ItemResult(float(p["language_quality"][key]))
    elif item.criterion == "fluency":
        result = ItemResult(float(p["fluency"][FLUENCY_KEYS[item.type]]))
    else:
        raise ValueError(f"Unknown criterion {item.criterion}")
    if item.override is not None:
        result = ItemResult(max(0.0, float(item.override)), needs_review=False)
    result.deduction = round(result.deduction, 2)
    return result


def segment_totals(items: list[Item], cfg: dict) -> tuple[Totals, list[ItemResult]]:
    results = [item_deduction(i, cfg) for i in items]
    t = Totals()
    for item, r in zip(items, results, strict=True):
        setattr(t, item.criterion, round(getattr(t, item.criterion) + r.deduction, 2))
    return t, results


def dialogue_score(segments: list[Totals], maximum: float, passing: float, cfg: dict) -> DialogueScore:
    total = Totals()
    for s in segments:
        total = total.add(s)
    score = maximum - total.total
    if cfg.get("floor_at_zero", True):
        score = max(0.0, score)
    return DialogueScore(total, round(score, 2), maximum, passing)


def mock_score(dialogues: list[DialogueScore], pass_total: float) -> MockScore:
    total = round(sum(d.score for d in dialogues), 2)
    maximum = round(sum(d.maximum for d in dialogues), 2)
    reasons = []
    if total < pass_total:
        reasons.append(f"Total {total:g} is below the pass mark of {pass_total:g}.")
    for i, d in enumerate(dialogues, start=1):
        if not d.passed:
            reasons.append(f"Dialogue {i} scored {d.score:g}, below the minimum of {d.passing:g}.")
    return MockScore(total, maximum, not reasons, reasons)
