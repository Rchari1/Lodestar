"""Momentum / trend-following strategy.

Uses MACD crossovers, RSI, and ADX to detect and ride trends.
"""

from __future__ import annotations

import logging

import pandas as pd

from lodestar.brokers.base import BaseBroker
from lodestar.models.trade import Side, Signal, SignalStrength
from lodestar.strategies.base import BaseStrategy

logger = logging.getLogger("lodestar.strategies.momentum")


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    def __init__(
        self,
        broker: BaseBroker,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        adx_threshold: float = 25,
        **kwargs,
    ) -> None:
        super().__init__(broker, **kwargs)
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.adx_threshold = adx_threshold

    def evaluate(self, symbol: str, df: pd.DataFrame) -> Signal | None:
        if len(df) < 50:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        rsi = latest.get("rsi")
        macd = latest.get("macd")
        macd_signal = latest.get("macd_signal")
        macd_prev = prev.get("macd")
        macd_signal_prev = prev.get("macd_signal")
        adx = latest.get("adx")
        sma_20 = latest.get("sma_20")
        sma_50 = latest.get("sma_50")
        close = latest.get("close")

        if any(v is None or pd.isna(v) for v in [rsi, macd, macd_signal, adx, close]):
            return None

        # ---- BUY signals ----
        bullish_macd = (macd_prev < macd_signal_prev) and (macd > macd_signal)
        strong_trend = adx > self.adx_threshold
        above_sma = close > sma_20 if pd.notna(sma_20) else False

        if bullish_macd and strong_trend and rsi < self.rsi_overbought:
            strength = SignalStrength.STRONG_BUY if (rsi < 40 and above_sma) else SignalStrength.BUY
            confidence = min(0.95, 0.5 + (adx / 100) + ((self.rsi_overbought - rsi) / 200))
            return Signal(
                symbol=symbol,
                side=Side.BUY,
                strength=strength,
                strategy=self.name,
                confidence=round(confidence, 3),
                reason=(
                    f"MACD bullish crossover (ADX={adx:.1f}, RSI={rsi:.1f})"
                ),
            )

        # ---- SELL signals ----
        bearish_macd = (macd_prev > macd_signal_prev) and (macd < macd_signal)
        below_sma = close < sma_50 if pd.notna(sma_50) else False

        if bearish_macd and strong_trend and rsi > self.rsi_oversold:
            strength = SignalStrength.STRONG_SELL if (rsi > 65 and below_sma) else SignalStrength.SELL
            confidence = min(0.95, 0.5 + (adx / 100) + ((rsi - self.rsi_oversold) / 200))
            return Signal(
                symbol=symbol,
                side=Side.SELL,
                strength=strength,
                strategy=self.name,
                confidence=round(confidence, 3),
                reason=(
                    f"MACD bearish crossover (ADX={adx:.1f}, RSI={rsi:.1f})"
                ),
            )

        return None
