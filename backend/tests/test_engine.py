import copy

import pytest

from app.services.scoring.engine import Item, Totals, dialogue_score, item_deduction, mock_score, segment_totals
from app.settings import scoring_config

CFG = scoring_config()


def ded(criterion, type_, **kw):
    return item_deduction(Item(criterion, type_, **kw), CFG).deduction


def test_brief_penalties():
    # SCORING_BRIEF summary table
    assert ded("accuracy", "Omission") == 1 and ded("accuracy", "Distortion") == 1 and ded("accuracy", "Insertion") == 1
    assert ded("accuracy", "Correct") == 0
    for t in ("Grammar", "UnidiomaticUsage", "Register", "SentenceStructure"):
        assert ded("language", t) == 0.5
    for t in ("Pause", "StartDelay", "Hesitation", "SelfCorrection"):
        assert ded("fluency", t) == 0.5


def test_pronunciation_is_review_only_by_default():
    r = item_deduction(Item("language", "Pronunciation"), CFG)
    assert r.deduction == 0 and r.needs_review
    on = copy.deepcopy(CFG)
    on["pronunciation_auto_deduct"] = True
    assert item_deduction(Item("language", "Pronunciation"), on).deduction == 0.5


def test_meaning_unit_weight_and_switch():
    assert ded("accuracy", "Omission", weight=2) == 2
    assert ded("accuracy", "Insertion", weight=2) == 1  # insertions have no MU
    off = copy.deepcopy(CFG)
    off["penalties"]["accuracy_completeness"]["use_meaning_unit_weight"] = False
    assert item_deduction(Item("accuracy", "Omission", weight=2), off).deduction == 1


def test_penalties_come_from_config():
    cfg = copy.deepcopy(CFG)
    cfg["penalties"]["language_quality"]["grammar"] = 0.25
    cfg["penalties"]["fluency"]["pause"] = 1
    assert item_deduction(Item("language", "Grammar"), cfg).deduction == 0.25
    assert item_deduction(Item("fluency", "Pause"), cfg).deduction == 1


def test_admin_override_replaces_deduction():
    assert ded("accuracy", "Omission", override=0) == 0
    assert ded("language", "Pronunciation", override=0.5) == 0.5
    assert ded("fluency", "Pause", override=-3) == 0  # never negative


def test_segment_and_dialogue_totals_example():
    # The brief's example: 10:30 omitted, "morning" inserted, one unidiomatic phrase, one self-correction, a 4 s pause
    items = [Item("accuracy", "Correct"), Item("accuracy", "Correct"), Item("accuracy", "Omission"),
             Item("accuracy", "Insertion"), Item("language", "UnidiomaticUsage"), Item("fluency", "SelfCorrection"),
             Item("fluency", "Pause")]
    t, results = segment_totals(items, CFG)
    assert (t.accuracy, t.language, t.fluency, t.total) == (2, 0.5, 1, 3.5)
    d = dialogue_score([t, Totals(1, 0, 0.5)], 45, 29, CFG)
    assert d.score == 40 and d.deductions.total == 5 and d.passed


def test_floor_at_zero():
    d = dialogue_score([Totals(50, 3, 2)], 45, 29, CFG)
    assert d.score == 0 and not d.passed
    nofloor = {**CFG, "floor_at_zero": False}
    assert dialogue_score([Totals(50, 0, 0)], 45, 29, nofloor).score == -5


@pytest.mark.parametrize("scores,passed", [
    ((32, 31), True),     # 63 total, both >= 29
    ((35, 27.5), False),  # 62.5 total
    ((40, 28.5), False),  # 68.5 total but dialogue 2 below 29
    ((29, 34), True),
])
def test_pass_rules(scores, passed):
    dialogues = [dialogue_score([Totals(45 - s, 0, 0)], 45, 29, CFG) for s in scores]
    m = mock_score(dialogues, CFG["pass_total"])
    assert m.passed is passed and m.maximum == 90 and m.total == sum(scores)
    if not passed:
        assert m.reasons


def test_fail_reasons_name_the_right_dialogue():
    dialogues = [dialogue_score([Totals(5, 0, 0)], 45, 29, CFG), dialogue_score([Totals(20, 0, 0)], 45, 29, CFG)]
    m = mock_score(dialogues, CFG["pass_total"])
    assert not any("Dialogue 1 scored" in r for r in m.reasons) and any("Dialogue 2 scored 25" in r for r in m.reasons)
