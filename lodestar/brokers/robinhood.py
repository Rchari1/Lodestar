"""Robinhood broker integration using robin_stocks."""

from __future__ import annotations

import logging
from datetime import datetime

import robin_stocks.robinhood as rh

from lodestar.brokers.base import BaseBroker
from lodestar.config import RobinhoodSettings
from lodestar.models.trade import Position, Side, Trade

logger = logging.getLogger("lodestar.brokers.robinhood")


class RobinhoodBroker(BaseBroker):
    """Live Robinhood broker using the robin_stocks library."""

    def __init__(self, settings: RobinhoodSettings) -> None:
        self._settings = settings
        self._connected = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        try:
            login_kwargs: dict = {
                "username": self._settings.username,
                "password": self._settings.password,
                "store_session": True,
            }
            if self._settings.totp_secret:
                totp = rh.get_totp_code(self._settings.totp_secret)
                login_kwargs["mfa_code"] = totp
            elif self._settings.mfa_code:
                login_kwargs["mfa_code"] = self._settings.mfa_code

            rh.login(**login_kwargs)
            self._connected = True
            logger.info("Connected to Robinhood successfully")
            return True
        except Exception:
            logger.exception("Failed to connect to Robinhood")
            return False

    def disconnect(self) -> None:
        if self._connected:
            rh.logout()
            self._connected = False
            logger.info("Disconnected from Robinhood")

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------

    def get_account_equity(self) -> float:
        profile = rh.profiles.load_portfolio_profile()
        return float(profile.get("equity", 0))

    def get_cash_balance(self) -> float:
        profile = rh.profiles.load_account_profile()
        return float(profile.get("cash", 0))

    def get_positions(self) -> list[Position]:
        raw = rh.account.get_open_stock_positions()
        positions: list[Position] = []
        for item in raw:
            qty = float(item.get("quantity", 0))
            if qty <= 0:
                continue
            symbol = rh.stocks.get_symbol_by_url(item.get("instrument", ""))
            avg_cost = float(item.get("average_buy_price", 0))
            current = self.get_current_price(symbol) if symbol else 0.0
            positions.append(
                Position(
                    symbol=symbol or "UNKNOWN",
                    quantity=qty,
                    average_cost=avg_cost,
                    current_price=current,
                )
            )
        return positions

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_current_price(self, symbol: str) -> float:
        quotes = rh.stocks.get_latest_price(symbol)
        if quotes and quotes[0]:
            return float(quotes[0])
        return 0.0

    def get_price_history(
        self,
        symbol: str,
        interval: str = "day",
        span: str = "year",
    ) -> list[dict]:
        """Fetch historical prices from Robinhood.

        Parameters
        ----------
        interval : day | week | 5minute | 10minute | hour
        span     : day | week | month | 3month | year | 5year
        """
        raw = rh.stocks.get_stock_historicals(symbol, interval=interval, span=span)
        if not raw:
            return []
        return [
            {
                "timestamp": r.get("begins_at", ""),
                "open": float(r.get("open_price", 0)),
                "high": float(r.get("high_price", 0)),
                "low": float(r.get("low_price", 0)),
                "close": float(r.get("close_price", 0)),
                "volume": int(r.get("volume", 0)),
            }
            for r in raw
        ]

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
        logger.info("Placing %s %s order: %.4f shares of %s", order_type, side.value, quantity, symbol)
        try:
            if side == Side.BUY:
                if order_type == "limit" and limit_price is not None:
                    result = rh.orders.order_buy_limit(symbol, quantity, limit_price)
                else:
                    result = rh.orders.order_buy_market(symbol, quantity)
            else:
                if order_type == "limit" and limit_price is not None:
                    result = rh.orders.order_sell_limit(symbol, quantity, limit_price)
                else:
                    result = rh.orders.order_sell_market(symbol, quantity)

            order_id = result.get("id", "")
            price = float(result.get("price", 0) or self.get_current_price(symbol))
            status = result.get("state", "pending")

            trade = Trade(
                id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                strategy="manual",
                status=status,
                order_id=order_id,
                timestamp=datetime.utcnow(),
            )
            logger.info("Order placed: %s", trade.order_id)
            return trade

        except Exception as exc:
            logger.exception("Order failed for %s", symbol)
            return Trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=0,
                strategy="manual",
                status="failed",
                reason=str(exc),
            )

    def cancel_order(self, order_id: str) -> bool:
        try:
            rh.orders.cancel_stock_order(order_id)
            logger.info("Cancelled order %s", order_id)
            return True
        except Exception:
            logger.exception("Failed to cancel order %s", order_id)
            return False

    def get_order_status(self, order_id: str) -> str:
        info = rh.orders.get_stock_order_info(order_id)
        return info.get("state", "unknown") if info else "unknown"
