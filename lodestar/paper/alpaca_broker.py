"""Alpaca paper account behind the Broker protocol. Paper only: this never touches a live account."""
from __future__ import annotations

import os
from datetime import date

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import GetCalendarRequest, MarketOrderRequest
from dotenv import load_dotenv


class AlpacaPaperBroker:
    def __init__(self, key: str | None = None, secret: str | None = None):
        load_dotenv()
        key = key or os.environ.get("ALPACA_API_KEY")
        secret = secret or os.environ.get("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise SystemExit("ALPACA_API_KEY / ALPACA_SECRET_KEY are not set (copy .env.example to .env).")
        self.client = TradingClient(key, secret, paper=True)

    def equity(self) -> float:
        return float(self.client.get_account().equity)

    def positions(self) -> dict[str, int]:
        return {p.symbol: int(float(p.qty)) for p in self.client.get_all_positions()}

    def is_trading_day(self, today: date) -> bool:
        return bool(self.client.get_calendar(GetCalendarRequest(start=today, end=today)))

    def submit_opg(self, symbol: str, qty: int) -> str:
        order = self.client.submit_order(MarketOrderRequest(
            symbol=symbol,
            qty=abs(qty),
            side=OrderSide.BUY if qty > 0 else OrderSide.SELL,
            time_in_force=TimeInForce.OPG,
        ))
        return str(order.id)
