"""Portfolio manager — sizing, risk controls, and trade execution."""

from __future__ import annotations

import logging
from datetime import datetime, date

from lodestar.brokers.base import BaseBroker
from lodestar.config import TradingSettings
from lodestar.models.trade import PortfolioSnapshot, Position, Side, Signal, SignalStrength, Trade

logger = logging.getLogger("lodestar.portfolio.manager")


class PortfolioManager:
    """Decides *how much* to trade given a signal, and enforces risk limits."""

    def __init__(self, broker: BaseBroker, settings: TradingSettings) -> None:
        self.broker = broker
        self.settings = settings
        self._trades_today: list[Trade] = []
        self._trade_date: date = datetime.utcnow().date()

    # ------------------------------------------------------------------
    # Risk checks
    # ------------------------------------------------------------------

    def _reset_daily_counter(self) -> None:
        today = datetime.utcnow().date()
        if today != self._trade_date:
            self._trades_today = []
            self._trade_date = today

    def can_trade(self) -> bool:
        """Return True if daily trade limit has not been hit."""
        self._reset_daily_counter()
        return len(self._trades_today) < self.settings.max_daily_trades

    def check_stop_loss(self, position: Position) -> bool:
        """Return True if the position has hit the stop-loss threshold."""
        return position.unrealized_pnl_pct <= -self.settings.stop_loss_pct

    def check_take_profit(self, position: Position) -> bool:
        """Return True if the position has hit the take-profit threshold."""
        return position.unrealized_pnl_pct >= self.settings.take_profit_pct

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def compute_position_size(self, signal: Signal) -> float:
        """Determine how many shares to buy/sell.

        The base allocation is ``max_position_pct`` of total equity,
        scaled by the signal's confidence.
        """
        equity = self.broker.get_account_equity()
        max_allocation = equity * self.settings.max_position_pct
        allocation = max_allocation * signal.confidence

        price = self.broker.get_current_price(signal.symbol)
        if price <= 0:
            return 0.0

        shares = allocation / price

        # Robinhood supports fractional shares — round to 4 decimals
        return round(shares, 4)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_signal(self, signal: Signal) -> Trade | None:
        """Validate a signal against risk rules and execute it."""
        if not self.can_trade():
            logger.warning("Daily trade limit reached — skipping %s", signal.symbol)
            return None

        # For sell signals, verify we actually hold the stock
        if signal.side == Side.SELL:
            positions = {p.symbol: p for p in self.broker.get_positions()}
            pos = positions.get(signal.symbol)
            if not pos or pos.quantity <= 0:
                logger.debug("No position in %s to sell — skipping", signal.symbol)
                return None
            quantity = pos.quantity  # sell entire position
        else:
            quantity = self.compute_position_size(signal)

        if quantity <= 0:
            return None

        # Check if we have enough cash for buys
        if signal.side == Side.BUY:
            price = self.broker.get_current_price(signal.symbol)
            cost = price * quantity
            cash = self.broker.get_cash_balance()
            if cost > cash:
                quantity = round(cash / price * 0.98, 4)  # keep 2% buffer
                if quantity <= 0:
                    logger.warning("Insufficient cash for %s", signal.symbol)
                    return None

        trade = self.broker.place_order(
            symbol=signal.symbol,
            side=signal.side,
            quantity=quantity,
        )
        trade.strategy = signal.strategy
        trade.reason = signal.reason

        if trade.status != "failed":
            self._trades_today.append(trade)
            logger.info(
                "Executed %s %s %.4f %s @ $%.2f [%s]",
                signal.strategy,
                signal.side.value,
                quantity,
                signal.symbol,
                trade.price,
                signal.reason,
            )

        return trade

    def enforce_risk_limits(self) -> list[Trade]:
        """Check all positions against stop-loss / take-profit and close if hit."""
        closed: list[Trade] = []
        for pos in self.broker.get_positions():
            pos.current_price = self.broker.get_current_price(pos.symbol)

            reason = ""
            if self.check_stop_loss(pos):
                reason = f"Stop-loss triggered ({pos.unrealized_pnl_pct:+.2%})"
            elif self.check_take_profit(pos):
                reason = f"Take-profit triggered ({pos.unrealized_pnl_pct:+.2%})"

            if reason:
                signal = Signal(
                    symbol=pos.symbol,
                    side=Side.SELL,
                    strength=SignalStrength.STRONG_SELL,
                    strategy="risk_manager",
                    confidence=1.0,
                    reason=reason,
                )
                trade = self.execute_signal(signal)
                if trade:
                    closed.append(trade)

        return closed

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot(self) -> PortfolioSnapshot:
        """Build a point-in-time snapshot of the portfolio."""
        positions = self.broker.get_positions()
        for p in positions:
            p.current_price = self.broker.get_current_price(p.symbol)
        return PortfolioSnapshot(
            total_equity=self.broker.get_account_equity(),
            cash=self.broker.get_cash_balance(),
            positions=positions,
        )

    @property
    def trades_today(self) -> list[Trade]:
        self._reset_daily_counter()
        return list(self._trades_today)
