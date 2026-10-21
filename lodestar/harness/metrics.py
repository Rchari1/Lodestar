"""Performance metrics for a daily return series."""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

DAYS = 252


def daily_sharpe(r: pd.Series) -> float:
    sd = r.std(ddof=1)
    if not np.isfinite(sd) or sd < 1e-12:
        return 0.0
    return float(r.mean() / sd)


def sharpe(r: pd.Series) -> float:
    return daily_sharpe(r) * math.sqrt(DAYS)


def cagr(r: pd.Series) -> float:
    growth = float((1 + r).prod())
    if growth <= 0:
        return -1.0
    return growth ** (DAYS / len(r)) - 1


def max_drawdown(r: pd.Series) -> float:
    equity = (1 + r).cumprod()
    return float((equity / equity.cummax() - 1).min())


def annual_turnover(w: pd.DataFrame) -> float:
    daily = w.diff().abs().sum(axis=1)
    daily.iloc[0] = 0.0
    return float(daily.mean() * DAYS)


EULER_GAMMA = 0.5772156649015329


def deflated_sharpe(r: pd.Series, trial_daily_sharpes) -> float:
    """Deflated Sharpe ratio (Bailey & Lopez de Prado, 2014).

    The probability that the true Sharpe exceeds the best Sharpe you'd expect by luck
    after `len(trial_daily_sharpes)` tries. Sharpes are per-period (daily), not annualized.
    With fewer than two trials the benchmark is 0, which gives the probabilistic Sharpe.
    """
    z = NormalDist()
    sr = daily_sharpe(r)
    trials = np.asarray(list(trial_daily_sharpes), dtype=float)
    n = len(trials)
    if n >= 2:
        sd = math.sqrt(float(np.var(trials, ddof=1)))
        sr0 = sd * ((1 - EULER_GAMMA) * z.inv_cdf(1 - 1 / n)
                    + EULER_GAMMA * z.inv_cdf(1 - 1 / (n * math.e)))
    else:
        sr0 = 0.0
    g3 = float(r.skew())
    g4 = float(r.kurt()) + 3.0
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2
    if denom <= 0 or len(r) < 2:
        return 0.0
    return z.cdf((sr - sr0) * math.sqrt(len(r) - 1) / math.sqrt(denom))
