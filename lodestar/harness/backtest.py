"""Turn target weights into daily net returns.

Timing: the weight row for date t is decided after t's close and executed at t+1's
open, then held to t+2's open. Returns are indexed by the decision date t.
Positions are rebalanced to target daily, so there's no drift between rebalances.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lodestar.data.store import Bars

MAX_GROSS = 1.0
COST_BPS = 5.0


def normalize(w, bars: Bars, max_gross: float = MAX_GROSS) -> pd.DataFrame:
    if not isinstance(w, pd.DataFrame):
        raise TypeError(f"weights() must return a pandas DataFrame, got {type(w).__name__}")
    w = w.reindex(index=bars.index, columns=bars.symbols).astype(float)
    w = w.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    w = w.where(bars.open.notna(), 0.0)
    gross = w.abs().sum(axis=1)
    scale = (max_gross / gross).where(gross > max_gross, 1.0)
    return w.mul(scale, axis=0)
