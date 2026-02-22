"""Tests for technical analysis module."""

import numpy as np
import pandas as pd

from lodestar.analysis.technical import add_all_indicators, build_dataframe, compute_support_resistance


def _make_history(n: int = 100) -> list[dict]:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return [
        {
            "timestamp": f"2025-01-{i+1:02d}T00:00:00Z" if i < 28 else f"2025-02-{i-27:02d}T00:00:00Z",
            "open": float(closes[i] - abs(np.random.randn()) * 0.3),
            "high": float(closes[i] + abs(np.random.randn()) * 0.5),
            "low": float(closes[i] - abs(np.random.randn()) * 0.5),
            "close": float(closes[i]),
            "volume": int(np.random.randint(100_000, 10_000_000)),
        }
        for i in range(n)
    ]


def test_build_dataframe():
    history = _make_history(50)
    df = build_dataframe(history)
    assert not df.empty
    assert "close" in df.columns
    assert len(df) == 50


def test_build_dataframe_empty():
    df = build_dataframe([])
    assert df.empty


def test_add_all_indicators():
    df = build_dataframe(_make_history(100))
    df = add_all_indicators(df)
    for col in ["sma_20", "rsi", "macd", "bb_upper", "bb_lower", "atr", "obv"]:
        assert col in df.columns, f"Missing indicator: {col}"


def test_support_resistance():
    df = build_dataframe(_make_history(100))
    sr = compute_support_resistance(df, window=20)
    assert sr["support"] > 0
    assert sr["resistance"] >= sr["support"]
