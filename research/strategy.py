"""Baseline: 12-1 month time-series momentum across the ETF universe.

Hold, equally weighted, every ETF whose return from 12 months ago to 1 month ago
is positive. Rebalance monthly.
"""
import numpy as np
import pandas as pd

LOOKBACK = 252
SKIP = 21


def weights(bars):
    close = bars.close
    mom = close.shift(SKIP) / close.shift(LOOKBACK) - 1
    signal = (mom > 0).astype(float)
    w = signal.div(signal.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    # Rebalance on the last trading day of each month, hold in between.
    month_end = pd.Series(close.index.to_period("M"), index=close.index)
    is_rebalance = month_end != month_end.shift(-1)
    return w.where(is_rebalance).ffill().fillna(0.0)
