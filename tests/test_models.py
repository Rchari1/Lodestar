"""Tests for data models."""

from lodestar.models.trade import Position, Side, Signal, SignalStrength, Trade


def test_position_market_value():
    p = Position(symbol="AAPL", quantity=10, average_cost=150.0, current_price=160.0)
    assert p.market_value == 1600.0


def test_position_unrealized_pnl():
    p = Position(symbol="AAPL", quantity=10, average_cost=150.0, current_price=160.0)
    assert p.unrealized_pnl == 100.0


def test_position_pnl_pct():
    p = Position(symbol="AAPL", quantity=10, average_cost=100.0, current_price=110.0)
    assert abs(p.unrealized_pnl_pct - 0.10) < 1e-9


def test_position_zero_cost():
    p = Position(symbol="X", quantity=5, average_cost=0.0, current_price=10.0)
    assert p.unrealized_pnl_pct == 0.0


def test_signal_creation():
    s = Signal(
        symbol="MSFT",
        side=Side.BUY,
        strength=SignalStrength.BUY,
        strategy="momentum",
        confidence=0.75,
        reason="test",
    )
    assert s.symbol == "MSFT"
    assert s.confidence == 0.75


def test_trade_defaults():
    t = Trade(symbol="TSLA", side=Side.SELL, quantity=5, price=200.0, strategy="test")
    assert t.status == "pending"
    assert t.order_id == ""
