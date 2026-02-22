"""Tests for trading strategies."""

import numpy as np
import pandas as pd

from lodestar.brokers.paper import PaperBroker
from lodestar.models.trade import Side
from lodestar.strategies.momentum import MomentumStrategy
from lodestar.strategies.mean_reversion import MeanReversionStrategy


def _make_df_with_indicators(n: int = 60) -> pd.DataFrame:
    """Create a DataFrame with pre-computed indicator columns."""
    np.random.seed(123)
    closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "close": closes,
            "high": closes + abs(np.random.randn(n)) * 0.5,
            "low": closes - abs(np.random.randn(n)) * 0.5,
            "open": closes - np.random.randn(n) * 0.3,
            "volume": np.random.randint(1_000_000, 5_000_000, size=n),
        }
    )
    # Manually set indicators for controlled testing
    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["rsi"] = 50.0  # neutral
    df["adx"] = 30.0  # trending
    df["macd"] = 0.0
    df["macd_signal"] = 0.0
    df["bb_upper"] = df["close"] + 5
    df["bb_lower"] = df["close"] - 5
    df["bb_middle"] = df["close"]
    df["stoch_k"] = 50.0
    df["stoch_d"] = 50.0
    return df


def test_momentum_no_signal_when_flat():
    broker = PaperBroker()
    broker.connect()
    strategy = MomentumStrategy(broker)
    df = _make_df_with_indicators()
    # MACD flat — no crossover — should return None
    signal = strategy.evaluate("AAPL", df)
    assert signal is None


def test_momentum_buy_on_crossover():
    broker = PaperBroker()
    broker.connect()
    strategy = MomentumStrategy(broker)
    df = _make_df_with_indicators()
    # Simulate a bullish MACD crossover at the last two rows
    df.iloc[-2, df.columns.get_loc("macd")] = -0.5
    df.iloc[-2, df.columns.get_loc("macd_signal")] = 0.5
    df.iloc[-1, df.columns.get_loc("macd")] = 0.6
    df.iloc[-1, df.columns.get_loc("macd_signal")] = 0.4
    df.iloc[-1, df.columns.get_loc("rsi")] = 45
    df.iloc[-1, df.columns.get_loc("adx")] = 30

    signal = strategy.evaluate("AAPL", df)
    assert signal is not None
    assert signal.side == Side.BUY


def test_momentum_sell_on_crossover():
    broker = PaperBroker()
    broker.connect()
    strategy = MomentumStrategy(broker)
    df = _make_df_with_indicators()
    # Simulate a bearish MACD crossover
    df.iloc[-2, df.columns.get_loc("macd")] = 0.5
    df.iloc[-2, df.columns.get_loc("macd_signal")] = -0.5
    df.iloc[-1, df.columns.get_loc("macd")] = -0.6
    df.iloc[-1, df.columns.get_loc("macd_signal")] = -0.4
    df.iloc[-1, df.columns.get_loc("rsi")] = 55
    df.iloc[-1, df.columns.get_loc("adx")] = 30

    signal = strategy.evaluate("AAPL", df)
    assert signal is not None
    assert signal.side == Side.SELL


def test_mean_reversion_buy_at_lower_bb():
    broker = PaperBroker()
    broker.connect()
    strategy = MeanReversionStrategy(broker)
    df = _make_df_with_indicators()
    # Price below lower BB + oversold RSI
    df.iloc[-1, df.columns.get_loc("close")] = 90.0
    df.iloc[-1, df.columns.get_loc("bb_lower")] = 91.0
    df.iloc[-1, df.columns.get_loc("rsi")] = 20.0
    df.iloc[-1, df.columns.get_loc("bb_upper")] = 110.0

    signal = strategy.evaluate("AAPL", df)
    assert signal is not None
    assert signal.side == Side.BUY


def test_mean_reversion_no_signal_when_normal():
    broker = PaperBroker()
    broker.connect()
    strategy = MeanReversionStrategy(broker)
    df = _make_df_with_indicators()
    # Price within normal BB range
    signal = strategy.evaluate("AAPL", df)
    assert signal is None


def test_strategy_requires_minimum_data():
    broker = PaperBroker()
    broker.connect()
    strategy = MomentumStrategy(broker)
    df = _make_df_with_indicators(10)  # too short
    signal = strategy.evaluate("AAPL", df)
    assert signal is None
