import numpy as np
import pandas as pd
import pytest

from lodestar.data.store import Bars
from lodestar.harness.backtest import backtest, forward_open_returns, normalize


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


def _tiny_bars():
    idx = pd.bdate_range("2020-01-01", periods=5)
    opens = pd.DataFrame({"A": [100.0, 110.0, 121.0, 121.0, 133.1]}, index=idx)
    return Bars(opens, opens, opens, opens, opens * 0 + 1e6)


def test_forward_returns_are_next_open_to_open_after():
    b = _tiny_bars()
    fwd = forward_open_returns(b)
    # decision on day 0 -> enter at open[1]=110, exit at open[2]=121
    assert fwd["A"].iloc[0] == pytest.approx(0.10)
    assert fwd["A"].iloc[1] == pytest.approx(0.0)
    assert np.isnan(fwd["A"].iloc[-1])


def test_backtest_timing_and_costs():
    b = _tiny_bars()
    w = pd.DataFrame({"A": [1.0, 1.0, 0.0, 0.0, 0.0]}, index=b.index)
    r = backtest(w, b, cost_bps=5.0)
    assert len(r) == 3  # last two decision days have no realised return
    assert r.iloc[0] == pytest.approx(0.10 - 0.0005)  # buy 0 -> 1 costs 5 bps
    assert r.iloc[1] == pytest.approx(0.0)            # hold through a flat day
    assert r.iloc[2] == pytest.approx(-0.0005)        # sell 1 -> 0 costs 5 bps


def test_zero_cost_buy_and_hold_matches_price_path(bars):
    w = pd.DataFrame(0.0, index=bars.index, columns=bars.symbols)
    w["AAA"] = 1.0
    r = backtest(w, bars, cost_bps=0.0)
    growth = (1 + r).prod()
    expected = bars.open["AAA"].iloc[-1] / bars.open["AAA"].iloc[1]
    assert growth == pytest.approx(expected)
