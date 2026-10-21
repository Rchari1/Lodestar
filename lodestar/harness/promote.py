"""One-time holdout evaluation of a found strategy. Humans run this, never the agent.

Each strategy gets exactly one look at the holdout. Running it again is refused,
because re-checking until something passes would turn the holdout into more
research data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from lodestar.data.store import concat_bars, load_bars, read_split
from lodestar.harness.backtest import COST_BPS, backtest, normalize
from lodestar.harness.metrics import annual_turnover, cagr, max_drawdown, sharpe
from lodestar.harness.sandbox import TIMEOUT_S, run_strategy

APPROVE_HOLDOUT_SHARPE = 0.3


class AlreadyPromoted(RuntimeError):
    """This strategy has already been evaluated on the holdout."""


def read_promoted(paths) -> dict:
    return json.loads(paths.promoted.read_text()) if paths.promoted.exists() else {}


def promote(paths, attempt_id: str, threshold: float = APPROVE_HOLDOUT_SHARPE,
            cost_bps: float = COST_BPS, timeout: float = TIMEOUT_S) -> dict:
    src = paths.found / f"{attempt_id}.py"
    if not src.exists():
        raise FileNotFoundError(f"{attempt_id} is not in {paths.found}")
    promoted = read_promoted(paths)
    if attempt_id in promoted:
        raise AlreadyPromoted(f"{attempt_id} already used its holdout look")

    start = read_split(paths)
    bars = concat_bars(load_bars(paths.research_bars), load_bars(paths.holdout_bars))
    full, _ = run_strategy(src, bars, timeout=timeout)
    w = normalize(full, bars)
    r = backtest(w, bars, cost_bps)
    hr = r[r.index >= start]

    record = {
        "id": attempt_id,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "holdout_start": str(start.date()),
        "holdout_end": str(hr.index[-1].date()),
        "holdout_days": len(hr),
        "holdout_sharpe": round(sharpe(hr), 3),
        "holdout_cagr": round(cagr(hr), 4),
        "holdout_max_drawdown": round(max_drawdown(hr), 4),
        "holdout_turnover": round(annual_turnover(w.loc[hr.index]), 2),
        "threshold": threshold,
        "approved": bool(sharpe(hr) >= threshold),
    }
    promoted[attempt_id] = record
    paths.promoted.write_text(json.dumps(promoted, indent=2) + "\n")
    return record
