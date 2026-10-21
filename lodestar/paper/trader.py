"""Daily paper rebalance: approved strategies -> combined weights -> whole-share OPG orders.

Run before the US open. Orders are market-on-open, which matches the backtest's
"decide after close t, execute at open t+1" timing.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Callable, Protocol

import pandas as pd

from lodestar.harness.backtest import normalize
from lodestar.harness.promote import read_promoted
from lodestar.harness.sandbox import run_strategy

GROSS_BUFFER = 0.98  # leave a little cash for open-vs-close price moves
MAX_STALE_DAYS = 5


class Broker(Protocol):
    def equity(self) -> float: ...
    def positions(self) -> dict[str, int]: ...
    def is_trading_day(self, today: date) -> bool: ...
    def submit_opg(self, symbol: str, qty: int) -> str: ...


def combine(weight_rows: dict[str, pd.Series]) -> pd.Series:
    """Equal-weight average across strategies, treating a missing symbol as 0."""
    if not weight_rows:
        return pd.Series(dtype=float)
    return pd.DataFrame(weight_rows).fillna(0.0).mean(axis=1)


def target_shares(weights: pd.Series, equity: float, prices: pd.Series) -> dict[str, int]:
    out = {}
    for sym, w in weights.items():
        price = prices.get(sym)
        if not w or price is None or not price > 0:
            continue
        qty = int(w * equity / price)  # int() truncates toward zero, for shorts too
        if qty:
            out[sym] = qty
    return out


def diff_orders(targets: dict[str, int], positions: dict[str, int]) -> list[tuple[str, int]]:
    """Signed share deltas, sells first. A flip through zero only closes today."""
    orders = []
    for sym in sorted(set(targets) | set(positions)):
        tgt, pos = targets.get(sym, 0), positions.get(sym, 0)
        if pos and tgt and (tgt > 0) != (pos > 0):
            tgt = 0
        if tgt != pos:
            orders.append((sym, tgt - pos))
    return sorted(orders, key=lambda o: o[1] > 0)


def approved_ids(paths) -> list[str]:
    return sorted(i for i, rec in read_promoted(paths).items() if rec.get("approved"))


def run_paper(paths, broker: Broker, fetch: Callable, today: date, dry_run: bool = False) -> dict:
    if not broker.is_trading_day(today):
        return {"date": str(today), "status": "skipped", "reason": "not a trading day"}

    bars = fetch()
    last = bars.index[-1]
    if (pd.Timestamp(today) - last).days > MAX_STALE_DAYS:
        raise RuntimeError(f"stale data: last bar {last.date()} for trading day {today}")

    ids = approved_ids(paths)
    per_strategy = {}
    for sid in ids:
        full, _ = run_strategy(paths.found / f"{sid}.py", bars)
        per_strategy[sid] = normalize(full, bars).iloc[-1]
    combined = combine(per_strategy)

    equity = float(broker.equity())
    positions = broker.positions()
    prices = bars.close.iloc[-1]
    targets = target_shares(combined, equity * GROSS_BUFFER, prices)
    orders = diff_orders(targets, positions)

    sent = []
    for sym, qty in orders:
        order_id = None if dry_run else broker.submit_opg(sym, qty)
        sent.append({"symbol": sym, "qty": qty, "order_id": order_id})

    def nonzero(s):
        return {k: round(float(v), 6) for k, v in s.items() if abs(v) > 1e-9}

    ledger = {
        "date": str(today),
        "status": "rebalanced",
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_through": str(last.date()),
        "equity": equity,
        "strategies": ids,
        "strategy_weights": {sid: nonzero(w) for sid, w in per_strategy.items()},
        "combined_weights": nonzero(combined),
        "positions_before": positions,
        "targets": targets,
        "orders": sent,
        "dry_run": dry_run,
    }
    if not dry_run:
        paths.ledger.mkdir(parents=True, exist_ok=True)
        (paths.ledger / f"{today}.json").write_text(json.dumps(ledger, indent=2) + "\n")
    return ledger
