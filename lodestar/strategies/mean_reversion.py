"""Mean-reversion strategy.

Uses Bollinger Bands, RSI extremes, and stochastic oscillator to
detect oversold/overbought conditions for reversal trades.
"""

from __future__ import annotations

import logging

import pandas as pd

from lodestar.brokers.base import BaseBroker
from lodestar.models.trade import Side, Signal, SignalStrength
from lodestar.strategies.base import BaseStrategy

logger = logging.getLogger("lodestar.strategies.mean_reversion")


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def __init__(
        self,
        broker: BaseBroker,
        rsi_oversold: float = 25,
        rsi_overbought: float = 75,
        bb_lookback: int = 5,
        **kwargs,
    ) -> None:
        super().__init__(broker, **kwargs)
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_lookback = bb_lookback

    def evaluate(self, symbol: str, df: pd.DataFrame) -> Signal | None:
        if len(df) < 30:
            return None

        latest = df.iloc[-1]
        close = latest.get("close")
        rsi = latest.get("rsi")
        bb_lower = latest.get("bb_lower")
        bb_upper = latest.get("bb_upper")
        bb_middle = latest.get("bb_middle")
        stoch_k = latest.get("stoch_k")
        stoch_d = latest.get("stoch_d")

        if any(
            v is None or pd.isna(v)
            for v in [close, rsi, bb_lower, bb_upper, bb_middle]
        ):
            return None

        # Count how many of the last N closes were below the lower BB
        recent_closes = df["close"].tail(self.bb_lookback)
        recent_bb_lower = df["bb_lower"].tail(self.bb_lookback)
        touches_lower = (recent_closes <= recent_bb_lower).sum()

        recent_bb_upper = df["bb_upper"].tail(self.bb_lookback)
        touches_upper = (recent_closes >= recent_bb_upper).sum()

        # ---- BUY: price near lower BB + RSI oversold ----
        if close <= bb_lower and rsi < self.rsi_oversold:
            is_strong = touches_lower >= 2 and (
                pd.notna(stoch_k) and stoch_k < 20
            )
            strength = SignalStrength.STRONG_BUY if is_strong else SignalStrength.BUY
            confidence = min(0.90, 0.4 + (self.rsi_oversold - rsi) / 100 + touches_lower * 0.05)
            return Signal(
                symbol=symbol,
                side=Side.BUY,
                strength=strength,
                strategy=self.name,
                confidence=round(confidence, 3),
                reason=(
                    f"Price at lower BB (RSI={rsi:.1f}, "
                    f"BB touches={touches_lower})"
                ),
            )

        # ---- SELL: price near upper BB + RSI overbought ----
        if close >= bb_upper and rsi > self.rsi_overbought:
            is_strong = touches_upper >= 2 and (
                pd.notna(stoch_k) and stoch_k > 80
            )
            strength = SignalStrength.STRONG_SELL if is_strong else SignalStrength.SELL
            confidence = min(0.90, 0.4 + (rsi - self.rsi_overbought) / 100 + touches_upper * 0.05)
            return Signal(
                symbol=symbol,
                side=Side.SELL,
                strength=strength,
                strategy=self.name,
                confidence=round(confidence, 3),
                reason=(
                    f"Price at upper BB (RSI={rsi:.1f}, "
                    f"BB touches={touches_upper})"
                ),
            )

        return None
