"""Property-based invariants of the deduction engine (hypothesis)."""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.scoring.engine import (ACCURACY_KEYS, FLUENCY_KEYS, LANGUAGE_KEYS, Item, Totals, dialogue_score,
                                         item_deduction, mock_score, segment_totals)
from app.settings import scoring_config

CFG = scoring_config()

items = st.one_of(
    st.builds(Item, st.just("accuracy"), st.sampled_from(sorted(ACCURACY_KEYS)), st.sampled_from([0.5, 1.0, 2.0]),
              st.one_of(st.none(), st.sampled_from([0.0, 0.5, 1.0, 3.0]))),
    st.builds(Item, st.just("language"), st.sampled_from(sorted(LANGUAGE_KEYS)), st.just(1.0),
              st.one_of(st.none(), st.sampled_from([0.0, 0.5]))),
    st.builds(Item, st.just("fluency"), st.sampled_from(sorted(FLUENCY_KEYS)), st.just(1.0),
              st.one_of(st.none(), st.sampled_from([0.0, 0.5]))),
)
segments = st.lists(st.lists(items, max_size=12), max_size=16)


def score(segs, maximum=45.0, passing=29.0):
    return dialogue_score([segment_totals(s, CFG)[0] for s in segs], maximum, passing, CFG)


@settings(max_examples=400, deadline=None)
@given(segments)
def test_score_is_bounded(segs):
    d = score(segs)
    assert 0 <= d.score <= 45
    assert d.deductions.total >= 0


@settings(max_examples=400, deadline=None)
@given(segments, items, st.integers(min_value=0, max_value=15))
def test_adding_an_error_never_raises_the_score(segs, extra, where):
    before = score(segs).score
    segs2 = [list(s) for s in segs] or [[]]
    segs2[where % len(segs2)].append(extra)
    assert score(segs2).score <= before


@settings(max_examples=300, deadline=None)
@given(st.lists(items, max_size=20))
def test_segment_total_is_sum_of_item_deductions(seg):
    totals, results = segment_totals(seg, CFG)
    assert abs(totals.total - sum(r.deduction for r in results)) < 1e-6
    assert all(r.deduction >= 0 for r in results)


@settings(max_examples=300, deadline=None)
@given(items)
def test_override_wins_and_clears_review(item):
    if item.override is not None:
        r = item_deduction(item, CFG)
        assert r.deduction == item.override and not r.needs_review


@settings(max_examples=300, deadline=None)
@given(st.lists(st.floats(min_value=0, max_value=45, allow_nan=False), min_size=2, max_size=2))
def test_mock_pass_rule(scores):
    ds = [dialogue_score([Totals(45 - s, 0, 0)], 45, 29, CFG) for s in scores]
    m = mock_score(ds, 63)
    expected = sum(d.score for d in ds) >= 63 and all(d.score >= 29 for d in ds)
    assert m.passed is expected
