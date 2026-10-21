"""Walk-forward folds over the research period.

Strategies are causal (the lookahead check enforces it), so scoring each fold on the
same full run is equivalent to re-running walk-forward with history up to each fold.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_FOLD_DAYS = 63  # about one quarter


def folds(index: pd.DatetimeIndex, n: int = 6, warmup: int = 252) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    scored = index[warmup:]
    if len(scored) < n * MIN_FOLD_DAYS:
        raise ValueError(f"need at least {n * MIN_FOLD_DAYS} days after warm-up, have {len(scored)}")
    chunks = np.array_split(np.arange(len(scored)), n)
    return [(scored[c[0]], scored[c[-1]]) for c in chunks]
