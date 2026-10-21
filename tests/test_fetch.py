import pandas as pd

from lodestar.data.fetch import bars_from_alpaca_df, completed_session_end


def _alpaca_frame():
    # alpaca-py returns MultiIndex (symbol, timestamp) with UTC timestamps at ET midnight.
    ts = pd.to_datetime(["2024-01-02 05:00", "2024-01-03 05:00", "2024-07-01 04:00"], utc=True)
    rows = []
    for sym, base in (("SPY", 470.0), ("TLT", 98.0)):
        for i, t in enumerate(ts):
            rows.append({"symbol": sym, "timestamp": t, "open": base + i, "high": base + i + 1,
                         "low": base + i - 1, "close": base + i + 0.5, "volume": 1e6,
                         "trade_count": 10, "vwap": base + i})
    return pd.DataFrame(rows).set_index(["symbol", "timestamp"])


def test_converts_to_naive_et_dates():
    bars = bars_from_alpaca_df(_alpaca_frame())
    assert list(bars.index) == list(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-07-01"]))
    assert bars.index.tz is None
    assert bars.symbols == ["SPY", "TLT"]
    assert bars.close.loc["2024-01-03", "TLT"] == 99.5


def test_completed_session_end_excludes_today():
    now = pd.Timestamp("2026-10-21 15:00", tz="UTC")  # 11:00 ET, market open
    end = completed_session_end(now)
    assert end < pd.Timestamp("2026-10-21 00:00", tz="America/New_York")
    assert end > pd.Timestamp("2026-10-20 23:59", tz="America/New_York")
