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
