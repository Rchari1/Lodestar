import json
from datetime import date

import pandas as pd
import pytest

from lodestar.paper.trader import combine, diff_orders, run_paper, target_shares
from lodestar.paths import Paths
from tests.conftest import make_bars


def test_combine_averages_with_missing_as_zero():
    a = pd.Series({"SPY": 0.6, "TLT": 0.4})
    b = pd.Series({"SPY": -0.2, "GLD": 0.5})
    c = combine({"a": a, "b": b})
    assert c["SPY"] == pytest.approx(0.2)
    assert c["TLT"] == pytest.approx(0.2)
    assert c["GLD"] == pytest.approx(0.25)


def test_combine_empty_is_empty():
    assert combine({}).empty


def test_target_shares_truncates_toward_zero():
    w = pd.Series({"SPY": 0.5, "TLT": -0.25, "GLD": 0.0})
    prices = pd.Series({"SPY": 300.0, "TLT": 90.0, "GLD": 180.0})
    t = target_shares(w, 10_000, prices)
    assert t == {"SPY": 16, "TLT": -27}


def test_diff_orders_sells_first_and_skips_zeros():
    orders = diff_orders({"SPY": 10, "TLT": 5}, {"SPY": 4, "TLT": 9, "GLD": 3})
    assert orders == [("GLD", -3), ("TLT", -4), ("SPY", 6)]


def test_diff_orders_flips_close_first():
    # long 10 -> short 5 only closes today; the short opens on the next run
    assert diff_orders({"SPY": -5}, {"SPY": 10}) == [("SPY", -10)]
    assert diff_orders({"SPY": 7}, {"SPY": -3}) == [("SPY", 3)]


class FakeBroker:
    def __init__(self, trading=True, equity=100_000.0, positions=None):
        self.trading, self._equity, self._positions = trading, equity, positions or {}
        self.submitted = []

    def equity(self):
        return self._equity

    def positions(self):
        return dict(self._positions)

    def is_trading_day(self, today):
        return self.trading

    def submit_opg(self, symbol, qty):
        self.submitted.append((symbol, qty))
        return f"order-{len(self.submitted)}"


LONG_AAA = '''
import pandas as pd

def weights(bars):
    w = pd.DataFrame(0.0, index=bars.index, columns=bars.symbols)
    w["AAA"] = 0.5
    w["BBB"] = -0.25
    return w
'''


@pytest.fixture
def paths(tmp_path):
    p = Paths.at(tmp_path)
    p.found.mkdir(parents=True)
    (p.found / "0001-a.py").write_text(LONG_AAA)
    p.promoted.write_text(json.dumps({
        "0001-a": {"approved": True}, "0002-b": {"approved": False}}))
    return p


TODAY = date(2023, 2, 1)


def fetch():
    bars = make_bars(1100, start="2019-03-01")
    return bars.truncate(pd.Timestamp("2023-01-31"))


def test_run_paper_submits_orders_and_writes_ledger(paths):
    broker = FakeBroker()
    out = run_paper(paths, broker, fetch, TODAY)
    assert out["status"] == "rebalanced"
    syms = [s for s, _ in broker.submitted]
    assert syms == ["BBB", "AAA"]  # the short (a sell) goes first
    led = json.loads((paths.ledger / "2023-02-01.json").read_text())
    assert led["strategies"] == ["0001-a"]
    assert led["equity"] == 100_000.0
    assert led["orders"][0]["order_id"] == "order-1"


def test_dry_run_submits_nothing_and_writes_no_ledger(paths):
    broker = FakeBroker()
    out = run_paper(paths, broker, fetch, TODAY, dry_run=True)
    assert broker.submitted == []
    assert out["orders"]
    assert not paths.ledger.exists()


def test_non_trading_day_skips(paths):
    broker = FakeBroker(trading=False)
    out = run_paper(paths, broker, fetch, TODAY)
    assert out["status"] == "skipped"
    assert broker.submitted == []


def test_no_approved_strategies_flattens_and_logs_equity(paths):
    paths.promoted.write_text(json.dumps({"0001-a": {"approved": False}}))
    broker = FakeBroker(positions={"SPY": 5})
    out = run_paper(paths, broker, fetch, TODAY)
    assert broker.submitted == [("SPY", -5)]
    assert out["strategies"] == []


def test_stale_data_raises_before_trading(paths):
    broker = FakeBroker()
    with pytest.raises(RuntimeError, match="stale"):
        run_paper(paths, broker, fetch, date(2023, 3, 1))
    assert broker.submitted == []
