"""Data models for trades, positions, and signals."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SignalStrength(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class Signal(BaseModel):
    """A trading signal produced by a strategy."""

    symbol: str
    side: Side
    strength: SignalStrength
    strategy: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Trade(BaseModel):
    """A completed or pending trade."""

    id: str = ""
    symbol: str
    side: Side
    quantity: float
    price: float
    strategy: str
    status: str = "pending"  # pending | filled | cancelled | failed
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: str = ""
    reason: str = ""


class Position(BaseModel):
    """A current portfolio position."""

    symbol: str
    quantity: float
    average_cost: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.average_cost) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.average_cost == 0:
            return 0.0
        return (self.current_price - self.average_cost) / self.average_cost


class PortfolioSnapshot(BaseModel):
    """Point-in-time snapshot of the portfolio."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_equity: float = 0.0
    cash: float = 0.0
    positions: list[Position] = Field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
