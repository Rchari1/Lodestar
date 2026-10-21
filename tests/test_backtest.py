import numpy as np
import pandas as pd
import pytest

from lodestar.data.store import Bars
from lodestar.harness.backtest import normalize


def _w(bars, value=0.0):
    return pd.DataFrame(value, index=bars.index, columns=bars.symbols)


def test_nan_becomes_zero(bars):
    w = _w(bars, np.nan)
    assert (normalize(w, bars) == 0).all().all()


def test_gross_above_one_is_scaled_down(bars):
    w = _w(bars, 0.5)  # 4 symbols -> gross 2.0
    n = normalize(w, bars)
    assert np.allclose(n.abs().sum(axis=1), 1.0)
    assert np.allclose(n, 0.25)


def test_gross_below_one_untouched(bars):
    w = _w(bars, 0.0)
    w["AAA"] = -0.3
    w["BBB"] = 0.2
    n = normalize(w, bars)
    assert np.allclose(n["AAA"], -0.3) and np.allclose(n["BBB"], 0.2)


def test_symbols_without_price_are_zeroed(bars):
    opens = bars.open.copy()
    opens.iloc[:100, 0] = np.nan
    b = Bars(opens, bars.high, bars.low, bars.close, bars.volume)
    n = normalize(_w(b, 0.25), b)
    assert (n.iloc[:100, 0] == 0).all()
    assert (n.iloc[200:, 0] == 0.25).all()


def test_reindexes_and_drops_unknown_columns(bars):
    w = _w(bars, 0.1).iloc[::2]
    w["ZZZ"] = 1.0
    n = normalize(w, bars)
    assert list(n.columns) == bars.symbols
    assert n.index.equals(bars.index)
    assert (n.iloc[1] == 0).all()


def test_rejects_non_dataframe(bars):
    with pytest.raises(TypeError):
        normalize(np.zeros((3, 3)), bars)
