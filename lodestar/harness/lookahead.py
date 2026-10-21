"""Detect use of future data by re-running a strategy on truncated history.

A causal strategy's weight for date d can depend only on data up to d, so cutting
off everything after some cutoff >= d must not change it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pick_cutoffs(index: pd.DatetimeIndex, n: int = 5, seed: int = 0, min_rows: int = 300) -> list[pd.Timestamp]:
    rng = np.random.default_rng(seed)
    positions = rng.choice(np.arange(min_rows, len(index) - 1), size=n, replace=False)
    return [index[p] for p in sorted(positions)]


def _clean(w, index, columns) -> pd.DataFrame:
    w = w.reindex(index=index, columns=columns).astype(float)
    return w.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def compare(full: pd.DataFrame, cuts: dict, tol: float = 1e-9) -> str | None:
    """None if consistent; otherwise a message naming the first offending date."""
    columns = full.columns
    for cutoff, cut in cuts.items():
        index = full.index[full.index <= cutoff]
        a = _clean(full, index, columns)
        b = _clean(cut, index, columns)
        diff = (a - b).abs().max(axis=1)
        bad = diff[diff > tol]
        if len(bad):
            return (f"lookahead: weights on {bad.index[0].date()} change when data after "
                    f"{pd.Timestamp(cutoff).date()} is removed (max diff {bad.iloc[0]:.3g})")
    return None
