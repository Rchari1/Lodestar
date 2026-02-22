"""Technical analysis indicators built on top of pandas + ta library."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import ta

logger = logging.getLogger("lodestar.analysis.technical")


def build_dataframe(history: list[dict]) -> pd.DataFrame:
    """Convert raw price history dicts into a clean DataFrame."""
    df = pd.DataFrame(history)
    if df.empty:
        return df
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df.sort_values("timestamp", inplace=True)
        df.set_index("timestamp", inplace=True)
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich a OHLCV DataFrame with a broad set of technical indicators."""
    if df.empty or "close" not in df.columns:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)

    # --- Trend ---
    df["sma_20"] = ta.trend.sma_indicator(close, window=20)
    df["sma_50"] = ta.trend.sma_indicator(close, window=50)
    df["ema_12"] = ta.trend.ema_indicator(close, window=12)
    df["ema_26"] = ta.trend.ema_indicator(close, window=26)

    macd = ta.trend.MACD(close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    adx = ta.trend.ADXIndicator(high, low, close)
    df["adx"] = adx.adx()

    # --- Momentum ---
    df["rsi"] = ta.momentum.rsi(close, window=14)
    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # --- Volatility ---
    bb = ta.volatility.BollingerBands(close)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = bb.bollinger_wband()
    df["atr"] = ta.volatility.average_true_range(high, low, close)

    # --- Volume ---
    df["obv"] = ta.volume.on_balance_volume(close, volume)
    df["vwap"] = np.cumsum(close * volume) / np.cumsum(volume)

    return df


def compute_support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    """Return simple rolling support & resistance levels."""
    if df.empty:
        return {"support": 0.0, "resistance": 0.0}
    recent = df.tail(window)
    return {
        "support": float(recent["low"].min()),
        "resistance": float(recent["high"].max()),
    }
