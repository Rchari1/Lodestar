import pandas as pd

from lodestar.harness.lookahead import compare, pick_cutoffs


def _run(fn, bars, cutoffs):
    return fn(bars), {c: fn(bars.truncate(c)) for c in cutoffs}


def causal(bars):
    return (bars.close / bars.close.rolling(50).mean() - 1).clip(-0.25, 0.25)


def peeks(bars):
    return (bars.close.shift(-1) > bars.close).astype(float) * 0.25


def peeks_via_global_stat(bars):
    # Subtle leak: normalising by a full-sample mean uses future data.
    z = bars.close.pct_change()
    return (z - z.mean()).clip(-0.25, 0.25)


def test_cutoffs_are_deterministic_and_in_range(bars):
    a = pick_cutoffs(bars.index, n=5, seed=7)
    assert a == pick_cutoffs(bars.index, n=5, seed=7)
    assert len(a) == 5 and len(set(a)) == 5
    assert all(bars.index[300] <= c < bars.index[-1] for c in a)


def test_causal_strategy_passes(bars):
    full, cuts = _run(causal, bars, pick_cutoffs(bars.index))
    assert compare(full, cuts) is None


def test_shift_minus_one_is_caught(bars):
    full, cuts = _run(peeks, bars, pick_cutoffs(bars.index))
    msg = compare(full, cuts)
    assert msg is not None and "lookahead" in msg


def test_full_sample_statistic_is_caught(bars):
    full, cuts = _run(peeks_via_global_stat, bars, pick_cutoffs(bars.index))
    assert compare(full, cuts) is not None
