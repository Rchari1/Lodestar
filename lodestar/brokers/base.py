"""Abstract base class for brokerage integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from lodestar.models.trade import Position, Side, Trade


class BaseBroker(ABC):
    """Interface that every broker adapter must implement."""

    @abstractmethod
    def connect(self) -> bool:
        """Authenticate and establish a session. Returns True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up the session."""

    @abstractmethod
    def get_account_equity(self) -> float:
        """Return total account equity (cash + positions)."""

    @abstractmethod
    def get_cash_balance(self) -> float:
        """Return available cash for trading."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return all open positions."""

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Return the latest price for a symbol."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        order_type: str = "market",
        limit_price: float | None = None,
    ) -> Trade:
        """Place an order and return the Trade record."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True on success."""

    @abstractmethod
    def get_order_status(self, order_id: str) -> str:
        """Return the status string of an order."""

    def get_price_history(
        self,
        symbol: str,
        interval: str = "day",
        span: str = "year",
    ) -> list[dict]:
        """Return historical price data. Override for real data."""
        return []
