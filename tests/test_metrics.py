import numpy as np
import pandas as pd
import pytest

from lodestar.harness.metrics import annual_turnover, cagr, daily_sharpe, max_drawdown, sharpe


def test_sharpe_of_constant_series_is_zero():
    assert sharpe(pd.Series([0.001] * 100)) == 0.0


def test_sharpe_annualizes_daily():
    r = pd.Series(np.random.default_rng(0).normal(0.0005, 0.01, 2000))
    assert sharpe(r) == pytest.approx(daily_sharpe(r) * np.sqrt(252))


def test_max_drawdown():
    r = pd.Series([0.10, -0.50, 0.20])  # equity 1.1 -> 0.55 -> 0.66
    assert max_drawdown(r) == pytest.approx(-0.5)


def test_cagr_of_constant_daily_return():
    r = pd.Series([0.001] * 252)
    assert cagr(r) == pytest.approx(1.001 ** 252 - 1)


def test_annual_turnover():
    idx = pd.bdate_range("2020-01-01", periods=4)
    w = pd.DataFrame({"A": [0.0, 1.0, 1.0, 0.0]}, index=idx)
    # daily |dw|: 0, 1, 0, 1 -> mean 0.5 -> x252
    assert annual_turnover(w) == pytest.approx(0.5 * 252)
