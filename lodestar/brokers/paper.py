"""Paper-trading broker for simulation and testing."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from lodestar.brokers.base import BaseBroker
from lodestar.models.trade import Position, Side, Trade

logger = logging.getLogger("lodestar.brokers.paper")


class PaperBroker(BaseBroker):
    """Simulated broker that tracks positions in memory.

    Uses a real broker's ``get_current_price`` and ``get_price_history``
    for market data but never places real orders.
    """

    def __init__(
        self,
        starting_cash: float = 100_000.0,
        market_data_broker: BaseBroker | None = None,
    ) -> None:
        self._cash = starting_cash
        self._starting_cash = starting_cash
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Trade] = {}
        self._connected = False
        self._market = market_data_broker  # delegate price lookups

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        self._connected = True
        logger.info(
            "Paper broker connected (starting cash: $%.2f)", self._starting_cash
        )
        return True

    def disconnect(self) -> None:
        self._connected = False

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------

    def get_account_equity(self) -> float:
        positions_value = sum(p.market_value for p in self._positions.values())
        return self._cash + positions_value

    def get_cash_balance(self) -> float:
        return self._cash

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    # ------------------------------------------------------------------
    # Market data — delegate to a real broker when available
    # ------------------------------------------------------------------

    def get_current_price(self, symbol: str) -> float:
        if self._market:
            return self._market.get_current_price(symbol)
        logger.warning("No market data source; returning 0 for %s", symbol)
        return 0.0

    def get_price_history(
        self,
        symbol: str,
        interval: str = "day",
        span: str = "year",
    ) -> list[dict]:
        if self._market:
            return self._market.get_price_history(symbol, interval=interval, span=span)
        return []

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        order_type: str = "market",
        limit_price: float | None = None,
    ) -> Trade:
        price = limit_price if (order_type == "limit" and limit_price) else self.get_current_price(symbol)
        cost = price * quantity

        if side == Side.BUY:
            if cost > self._cash:
                return Trade(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    strategy="paper",
                    status="failed",
                    reason="Insufficient paper cash",
                )
            self._cash -= cost
            pos = self._positions.get(symbol)
            if pos:
                new_qty = pos.quantity + quantity
                pos.average_cost = (
                    (pos.average_cost * pos.quantity) + (price * quantity)
                ) / new_qty
                pos.quantity = new_qty
                pos.current_price = price
            else:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    average_cost=price,
                    current_price=price,
                )
        else:  # SELL
            pos = self._positions.get(symbol)
            if not pos or pos.quantity < quantity:
                return Trade(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    strategy="paper",
                    status="failed",
                    reason="Insufficient shares to sell",
                )
            self._cash += cost
            pos.quantity -= quantity
            if pos.quantity <= 0:
                del self._positions[symbol]

        order_id = uuid.uuid4().hex[:12]
        trade = Trade(
            id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            strategy="paper",
            status="filled",
            order_id=order_id,
            timestamp=datetime.utcnow(),
        )
        self._orders[order_id] = trade
        logger.info(
            "[PAPER] %s %.4f %s @ $%.2f", side.value.upper(), quantity, symbol, price
        )
        return trade

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id].status = "cancelled"
            return True
        return False

    def get_order_status(self, order_id: str) -> str:
        trade = self._orders.get(order_id)
        return trade.status if trade else "unknown"
