import numpy as np
import pandas as pd
import pytest

from lodestar.data.store import Bars


def make_bars(n_days: int = 1800, symbols=("AAA", "BBB", "CCC", "DDD"), seed: int = 0,
              start: str = "2016-01-04", drift=None) -> Bars:
    """Synthetic daily OHLCV from a geometric random walk, with a little drift per symbol."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n_days)
    cols = list(symbols)
    drift = np.linspace(0.0001, 0.0004, len(cols)) if drift is None else np.asarray(drift)
    rets = rng.normal(drift, 0.01, size=(n_days, len(cols)))
    close = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=cols)
    gap = pd.DataFrame(rng.normal(0, 0.002, size=close.shape), index=idx, columns=cols)
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + gap)
    high = np.maximum(open_, close) * 1.003
    low = np.minimum(open_, close) * 0.997
    volume = pd.DataFrame(rng.integers(1_000_000, 5_000_000, size=close.shape), index=idx,
                          columns=cols).astype(float)
    return Bars(open=open_, high=high, low=low, close=close, volume=volume)


@pytest.fixture
def bars() -> Bars:
    return make_bars()
