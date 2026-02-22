"""Sentiment-driven strategy.

Combines news headline sentiment with basic technical confirmation
(RSI and SMA) to generate signals.
"""

from __future__ import annotations

import logging

import pandas as pd

from lodestar.analysis.sentiment import get_combined_sentiment
from lodestar.brokers.base import BaseBroker
from lodestar.models.trade import Side, Signal, SignalStrength
from lodestar.strategies.base import BaseStrategy

logger = logging.getLogger("lodestar.strategies.sentiment")


class SentimentStrategy(BaseStrategy):
    name = "sentiment"

    def __init__(
        self,
        broker: BaseBroker,
        bullish_threshold: float = 0.15,
        bearish_threshold: float = -0.15,
        news_api_key: str = "",
        **kwargs,
    ) -> None:
        super().__init__(broker, **kwargs)
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.news_api_key = news_api_key

    def evaluate(self, symbol: str, df: pd.DataFrame) -> Signal | None:
        if len(df) < 20:
            return None

        # ---- Sentiment score ----
        result = get_combined_sentiment(symbol, news_api_key=self.news_api_key)
        score = result.score
        if abs(score) < 0.05:
            return None  # neutral — skip

        latest = df.iloc[-1]
        rsi = latest.get("rsi")
        sma_20 = latest.get("sma_20")
        close = latest.get("close")

        if any(v is None or pd.isna(v) for v in [rsi, sma_20, close]):
            return None

        # ---- Bullish sentiment + technical confirmation ----
        if score >= self.bullish_threshold and rsi < 65 and close > sma_20:
            strength = SignalStrength.STRONG_BUY if score > 0.3 else SignalStrength.BUY
            confidence = min(0.85, 0.3 + abs(score) + (65 - rsi) / 200)
            return Signal(
                symbol=symbol,
                side=Side.BUY,
                strength=strength,
                strategy=self.name,
                confidence=round(confidence, 3),
                reason=(
                    f"Bullish sentiment ({score:+.2f}) confirmed by "
                    f"RSI={rsi:.1f}, price above SMA20"
                ),
            )

        # ---- Bearish sentiment + technical confirmation ----
        if score <= self.bearish_threshold and rsi > 40 and close < sma_20:
            strength = SignalStrength.STRONG_SELL if score < -0.3 else SignalStrength.SELL
            confidence = min(0.85, 0.3 + abs(score) + (rsi - 40) / 200)
            return Signal(
                symbol=symbol,
                side=Side.SELL,
                strength=strength,
                strategy=self.name,
                confidence=round(confidence, 3),
                reason=(
                    f"Bearish sentiment ({score:+.2f}) confirmed by "
                    f"RSI={rsi:.1f}, price below SMA20"
                ),
            )

        return None
