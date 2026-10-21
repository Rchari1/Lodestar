import pandas as pd
import pytest

from lodestar.harness.splits import folds


def test_six_contiguous_non_overlapping_folds():
    idx = pd.bdate_range("2016-01-04", periods=2400)
    fs = folds(idx, n=6, warmup=252)
    assert len(fs) == 6
    assert fs[0][0] == idx[252]
    assert fs[-1][1] == idx[-1]
    for (s0, e0), (s1, e1) in zip(fs, fs[1:]):
        assert e0 < s1
        assert idx.get_loc(s1) == idx.get_loc(e0) + 1  # no gaps
    covered = sum(idx.get_loc(e) - idx.get_loc(s) + 1 for s, e in fs)
    assert covered == 2400 - 252


def test_too_little_data_raises():
    with pytest.raises(ValueError):
        folds(pd.bdate_range("2020-01-01", periods=400), n=6, warmup=252)
