"""Abstract base class for trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from lodestar.brokers.base import BaseBroker
from lodestar.models.trade import Signal


class BaseStrategy(ABC):
    """Every strategy must implement ``evaluate``."""

    name: str = "base"

    def __init__(self, broker: BaseBroker, **kwargs) -> None:  # noqa: ANN003
        self.broker = broker
        self.params = kwargs

    @abstractmethod
    def evaluate(self, symbol: str, df: pd.DataFrame) -> Signal | None:
        """Analyze the enriched DataFrame and return a Signal (or None to skip).

        Parameters
        ----------
        symbol : str
            The ticker to evaluate.
        df : pd.DataFrame
            OHLCV DataFrame with technical indicators already computed.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
