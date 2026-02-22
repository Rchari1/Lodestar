"""Core trading bot orchestrator."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from lodestar.analysis.screener import build_watchlist
from lodestar.analysis.technical import add_all_indicators, build_dataframe
from lodestar.brokers.base import BaseBroker
from lodestar.brokers.paper import PaperBroker
from lodestar.config import Settings
from lodestar.models.trade import PortfolioSnapshot, Signal, Trade
from lodestar.portfolio.manager import PortfolioManager
from lodestar.strategies import STRATEGY_REGISTRY
from lodestar.strategies.base import BaseStrategy

logger = logging.getLogger("lodestar.bot")


class TradingBot:
    """Main orchestrator that ties together broker, strategies, and portfolio."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.broker: BaseBroker = self._init_broker()
        self.portfolio = PortfolioManager(self.broker, settings.trading)
        self.strategies: list[BaseStrategy] = self._init_strategies()
        self.watchlist: list[str] = []

        # Audit trail
        self.trade_log: list[Trade] = []
        self.signal_log: list[Signal] = []
        self.snapshots: list[PortfolioSnapshot] = []

        self._running = False

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_broker(self) -> BaseBroker:
        from lodestar.brokers.robinhood import RobinhoodBroker

        rh_broker = RobinhoodBroker(self.settings.robinhood)
        if self.settings.trading.mode == "paper":
            logger.info("Starting in PAPER trading mode")
            return PaperBroker(starting_cash=100_000, market_data_broker=rh_broker)
        logger.info("Starting in LIVE trading mode")
        return rh_broker

    def _init_strategies(self) -> list[BaseStrategy]:
        strats: list[BaseStrategy] = []
        for name in self.settings.strategies.enabled_list:
            cls = STRATEGY_REGISTRY.get(name)
            if cls is None:
                logger.warning("Unknown strategy '%s' — skipping", name)
                continue
            kwargs = {}
            if name == "sentiment":
                kwargs["news_api_key"] = self.settings.news_api_key
            strats.append(cls(broker=self.broker, **kwargs))
            logger.info("Loaded strategy: %s", name)
        return strats

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Connect the broker(s)."""
        ok = self.broker.connect()
        if ok and isinstance(self.broker, PaperBroker) and self.broker._market:
            self.broker._market.connect()
        return ok

    def disconnect(self) -> None:
        self.broker.disconnect()

    def refresh_watchlist(self, custom: list[str] | None = None) -> list[str]:
        """Rebuild the watchlist from screener + custom symbols."""
        self.watchlist = build_watchlist(custom=custom, limit=20)
        logger.info("Watchlist (%d symbols): %s", len(self.watchlist), self.watchlist)
        return self.watchlist

    def scan_and_trade(self) -> list[Trade]:
        """One full cycle: scan watchlist → generate signals → execute trades."""
        trades: list[Trade] = []

        # 1. Enforce risk limits first (stop-loss / take-profit)
        closed = self.portfolio.enforce_risk_limits()
        trades.extend(closed)

        # 2. Evaluate each symbol with each strategy
        for symbol in self.watchlist:
            history = self.broker.get_price_history(symbol, interval="day", span="year")
            df = build_dataframe(history)
            if df.empty:
                continue
            df = add_all_indicators(df)

            for strategy in self.strategies:
                signal = strategy.evaluate(symbol, df)
                if signal is None:
                    continue
                self.signal_log.append(signal)
                logger.info(
                    "Signal: %s %s %s (%.1f%% confidence) — %s",
                    signal.strategy,
                    signal.side.value,
                    signal.symbol,
                    signal.confidence * 100,
                    signal.reason,
                )

                trade = self.portfolio.execute_signal(signal)
                if trade:
                    trades.append(trade)
                    self.trade_log.append(trade)

        # 3. Snapshot
        snap = self.portfolio.snapshot()
        self.snapshots.append(snap)
        logger.info(
            "Cycle complete — equity: $%.2f, cash: $%.2f, positions: %d, trades this cycle: %d",
            snap.total_equity,
            snap.cash,
            len(snap.positions),
            len(trades),
        )
        return trades

    def run(self, custom_watchlist: list[str] | None = None) -> None:
        """Run the bot in a continuous loop."""
        if not self.connect():
            logger.error("Failed to connect to broker — aborting")
            return

        self._running = True
        self.refresh_watchlist(custom=custom_watchlist)
        interval = self.settings.trading.interval_minutes * 60

        logger.info(
            "Bot started — mode=%s, interval=%dm, strategies=%s",
            self.settings.trading.mode,
            self.settings.trading.interval_minutes,
            [s.name for s in self.strategies],
        )

        try:
            while self._running:
                now = datetime.utcnow()
                # Basic market-hours check (9:30 - 16:00 ET, weekdays)
                # Simplified — a production system should use proper market calendars
                if now.weekday() < 5:
                    self.scan_and_trade()
                else:
                    logger.info("Weekend — skipping scan")

                logger.info("Sleeping %d minutes until next cycle...", self.settings.trading.interval_minutes)
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            self._running = False
            self.disconnect()

    def stop(self) -> None:
        self._running = False
