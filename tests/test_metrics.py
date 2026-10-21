import numpy as np
import pandas as pd
import pytest

from lodestar.harness.metrics import (annual_turnover, cagr, daily_sharpe, deflated_sharpe,
                                      max_drawdown, sharpe)


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


def _hand_dsr(r, trials):
    """Bailey & Lopez de Prado (2014), written out independently of the implementation."""
    from statistics import NormalDist
    Z = NormalDist()
    sr = r.mean() / r.std(ddof=1)
    g3, g4 = r.skew(), r.kurt() + 3
    n = len(trials)
    euler = 0.5772156649015329
    sr0 = np.sqrt(np.var(trials, ddof=1)) * ((1 - euler) * Z.inv_cdf(1 - 1 / n)
                                              + euler * Z.inv_cdf(1 - 1 / (n * np.e)))
    return Z.cdf((sr - sr0) * np.sqrt(len(r) - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))


def test_dsr_matches_hand_computation():
    r = pd.Series(np.random.default_rng(1).normal(0.0006, 0.01, 1500))
    trials = [0.01, 0.03, -0.02, 0.05, 0.00, 0.02, 0.04]
    assert deflated_sharpe(r, trials) == pytest.approx(_hand_dsr(r, trials))


def test_dsr_with_one_trial_is_probabilistic_sharpe_vs_zero():
    r = pd.Series(np.random.default_rng(2).normal(0.0006, 0.01, 1500))
    from statistics import NormalDist
    sr = r.mean() / r.std(ddof=1)
    g3, g4 = r.skew(), r.kurt() + 3
    psr = NormalDist().cdf(sr * np.sqrt(len(r) - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    assert deflated_sharpe(r, [0.02]) == pytest.approx(psr)


def test_more_trials_deflate_more():
    r = pd.Series(np.random.default_rng(3).normal(0.0006, 0.01, 1500))
    rng = np.random.default_rng(4)
    few = list(rng.normal(0, 0.02, 5))
    many = few + list(rng.normal(0, 0.02, 500))
    assert deflated_sharpe(r, many) < deflated_sharpe(r, few)
