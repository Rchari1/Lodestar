"""Tests for the portfolio manager."""

from lodestar.brokers.paper import PaperBroker
from lodestar.config import TradingSettings
from lodestar.models.trade import Position, Side, Signal, SignalStrength
from lodestar.portfolio.manager import PortfolioManager


class FixedPriceBroker(PaperBroker):
    """Paper broker with a fixed price for testing."""

    def __init__(self, price: float = 100.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._price = price

    def get_current_price(self, symbol: str) -> float:
        return self._price


def _make_manager(cash: float = 100_000, price: float = 100.0) -> PortfolioManager:
    broker = FixedPriceBroker(price=price, starting_cash=cash)
    broker.connect()
    settings = TradingSettings(
        max_position_pct=0.05,
        max_daily_trades=5,
        stop_loss_pct=0.03,
        take_profit_pct=0.08,
    )
    return PortfolioManager(broker, settings)


def _buy_signal(symbol: str = "AAPL", confidence: float = 0.8) -> Signal:
    return Signal(
        symbol=symbol,
        side=Side.BUY,
        strength=SignalStrength.BUY,
        strategy="test",
        confidence=confidence,
        reason="test signal",
    )


def _sell_signal(symbol: str = "AAPL") -> Signal:
    return Signal(
        symbol=symbol,
        side=Side.SELL,
        strength=SignalStrength.SELL,
        strategy="test",
        confidence=0.8,
        reason="test sell",
    )


def test_position_sizing():
    mgr = _make_manager()
    signal = _buy_signal(confidence=1.0)
    size = mgr.compute_position_size(signal)
    # max_position_pct=0.05, equity=100k → 5000 allocation, price=100 → 50 shares
    assert size == 50.0


def test_position_sizing_scales_with_confidence():
    mgr = _make_manager()
    signal = _buy_signal(confidence=0.5)
    size = mgr.compute_position_size(signal)
    # 5000 * 0.5 = 2500 allocation, price=100 → 25 shares
    assert size == 25.0


def test_execute_buy_signal():
    mgr = _make_manager()
    trade = mgr.execute_signal(_buy_signal())
    assert trade is not None
    assert trade.status == "filled"
    assert trade.side == Side.BUY


def test_execute_sell_needs_position():
    mgr = _make_manager()
    trade = mgr.execute_signal(_sell_signal())
    assert trade is None  # no position to sell


def test_execute_sell_with_position():
    mgr = _make_manager()
    mgr.execute_signal(_buy_signal())
    trade = mgr.execute_signal(_sell_signal())
    assert trade is not None
    assert trade.side == Side.SELL


def test_daily_trade_limit():
    mgr = _make_manager()
    # max_daily_trades = 5
    for i in range(5):
        trade = mgr.execute_signal(_buy_signal(symbol=f"SYM{i}"))
        assert trade is not None
    # 6th trade should be blocked
    trade = mgr.execute_signal(_buy_signal(symbol="SYM5"))
    assert trade is None


def test_stop_loss_check():
    mgr = _make_manager()
    pos = Position(symbol="X", quantity=10, average_cost=100.0, current_price=96.0)
    assert mgr.check_stop_loss(pos)  # -4% > -3% threshold


def test_take_profit_check():
    mgr = _make_manager()
    pos = Position(symbol="X", quantity=10, average_cost=100.0, current_price=110.0)
    assert mgr.check_take_profit(pos)  # +10% > +8% threshold


def test_snapshot():
    mgr = _make_manager()
    mgr.execute_signal(_buy_signal())
    snap = mgr.snapshot()
    assert snap.total_equity == 100_000
    assert len(snap.positions) == 1
