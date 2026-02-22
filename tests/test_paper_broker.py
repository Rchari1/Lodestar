"""Tests for the paper trading broker."""

from lodestar.brokers.paper import PaperBroker
from lodestar.models.trade import Side


class FakeMarket:
    """Minimal stub for market data."""

    def get_current_price(self, symbol: str) -> float:
        prices = {"AAPL": 180.0, "MSFT": 400.0, "TSLA": 250.0}
        return prices.get(symbol, 100.0)

    def get_price_history(self, symbol, interval="day", span="year"):
        return []


def make_broker(cash: float = 100_000) -> PaperBroker:
    return PaperBroker(starting_cash=cash, market_data_broker=FakeMarket())


def test_initial_state():
    b = make_broker()
    b.connect()
    assert b.get_cash_balance() == 100_000
    assert b.get_account_equity() == 100_000
    assert b.get_positions() == []


def test_buy_order():
    b = make_broker()
    b.connect()
    trade = b.place_order("AAPL", Side.BUY, 10)
    assert trade.status == "filled"
    assert trade.price == 180.0
    assert b.get_cash_balance() == 100_000 - 1800.0
    positions = b.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].quantity == 10


def test_sell_order():
    b = make_broker()
    b.connect()
    b.place_order("AAPL", Side.BUY, 10)
    trade = b.place_order("AAPL", Side.SELL, 5)
    assert trade.status == "filled"
    positions = b.get_positions()
    assert positions[0].quantity == 5


def test_sell_all_removes_position():
    b = make_broker()
    b.connect()
    b.place_order("MSFT", Side.BUY, 5)
    b.place_order("MSFT", Side.SELL, 5)
    assert b.get_positions() == []


def test_insufficient_cash():
    b = make_broker(cash=100)
    b.connect()
    trade = b.place_order("AAPL", Side.BUY, 10)  # costs 1800
    assert trade.status == "failed"


def test_insufficient_shares():
    b = make_broker()
    b.connect()
    trade = b.place_order("AAPL", Side.SELL, 10)
    assert trade.status == "failed"


def test_equity_includes_positions():
    b = make_broker(cash=10_000)
    b.connect()
    b.place_order("AAPL", Side.BUY, 10)  # 1800
    equity = b.get_account_equity()
    # cash = 10000 - 1800 = 8200, position value = 10*180 = 1800
    assert equity == 10_000


def test_cancel_order():
    b = make_broker()
    b.connect()
    trade = b.place_order("AAPL", Side.BUY, 1)
    assert b.cancel_order(trade.order_id)
    assert b.get_order_status(trade.order_id) == "cancelled"


def test_multiple_buys_average_cost():
    b = make_broker()
    b.connect()
    b.place_order("AAPL", Side.BUY, 10)  # 10 @ 180
    b.place_order("AAPL", Side.BUY, 10)  # 10 @ 180
    pos = b.get_positions()[0]
    assert pos.quantity == 20
    assert pos.average_cost == 180.0
