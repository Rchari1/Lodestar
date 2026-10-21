"""Score research/strategy.py on the research period and log the attempt.

This is the only scoring command the research agent can run. It never loads the holdout.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from lodestar.data.store import load_bars
from lodestar.harness.backtest import COST_BPS, backtest, normalize
from lodestar.harness.integrity import PACKAGE_DIR, verify_manifest
from lodestar.harness.lookahead import compare, pick_cutoffs
from lodestar.harness.metrics import (annual_turnover, cagr, daily_sharpe, deflated_sharpe,
                                      max_drawdown, sharpe)
from lodestar.harness.sandbox import TIMEOUT_S, StrategyError, run_strategy
from lodestar.harness.splits import folds

N_FOLDS = 6
WARMUP_DAYS = 252
PASS_MEAN_FOLD_SHARPE = 0.7
PASS_POSITIVE_FOLDS = 4
MAX_ABS_CORR = 0.7


class IntegrityError(RuntimeError):
    """The harness code differs from its manifest."""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] or "attempt"


def read_results(paths) -> list[dict]:
    if not paths.results.exists():
        return []
    return [json.loads(line) for line in paths.results.read_text().splitlines() if line.strip()]


def _append(paths, record: dict) -> None:
    paths.results.parent.mkdir(parents=True, exist_ok=True)
    with paths.results.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _found_returns(paths) -> dict[str, pd.Series]:
    out = {}
    if paths.found.exists():
        for f in sorted(paths.found.glob("*.returns.parquet")):
            out[f.name.removesuffix(".returns.parquet")] = pd.read_parquet(f)["ret"]
    return out


def score_returns(r: pd.Series, w: pd.DataFrame) -> dict:
    """Fold and full-period metrics on the scored (post warm-up) part of a return series."""
    fold_sharpes = [sharpe(r.loc[s:e]) for s, e in folds(r.index, N_FOLDS, WARMUP_DAYS)]
    scored = r.iloc[WARMUP_DAYS:]
    ws = w.loc[scored.index]
    return {
        "fold_sharpes": [round(x, 3) for x in fold_sharpes],
        "mean_fold_sharpe": round(sum(fold_sharpes) / len(fold_sharpes), 3),
        "min_fold_sharpe": round(min(fold_sharpes), 3),
        "positive_folds": sum(x > 0 for x in fold_sharpes),
        "sharpe": round(sharpe(scored), 3),
        "sr_daily": daily_sharpe(scored),
        "cagr": round(cagr(scored), 4),
        "max_drawdown": round(max_drawdown(scored), 4),
        "annual_turnover": round(annual_turnover(ws), 2),
        "avg_gross": round(float(ws.abs().sum(axis=1).mean()), 3),
        "start": str(scored.index[0].date()),
        "end": str(scored.index[-1].date()),
    }


def evaluate(paths, name: str, hypothesis: str, cost_bps: float = COST_BPS,
             check_integrity: bool = True, timeout: float = TIMEOUT_S,
             pkg_dir: Path = PACKAGE_DIR) -> dict:
    if check_integrity:
        problems = verify_manifest(pkg_dir)
        if problems:
            raise IntegrityError("harness integrity check failed: " + "; ".join(problems))

    prior = read_results(paths)
    number = len(prior) + 1
    attempt_id = f"{number:04d}-{slugify(name)}"
    source = paths.strategy.read_text()
    paths.attempts.mkdir(parents=True, exist_ok=True)
    (paths.attempts / f"{attempt_id}.py").write_text(source)

    record = {
        "id": attempt_id,
        "name": name,
        "hypothesis": hypothesis,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_sha256": hashlib.sha256(source.encode()).hexdigest()[:16],
        "cost_bps": cost_bps,
    }

    bars = load_bars(paths.research_bars)
    try:
        # Seeded per attempt, so the cutoff dates can't be learned and avoided.
        cutoffs = pick_cutoffs(bars.index, seed=number)
        full, cuts = run_strategy(paths.strategy, bars, cutoffs, timeout=timeout)
    except StrategyError as e:
        record |= {"status": "error", "reason": str(e)[-2000:], "passed": False}
        _append(paths, record)
        return record

    leak = compare(full, cuts)
    if leak:
        record |= {"status": "rejected", "reason": leak, "passed": False}
        _append(paths, record)
        return record

    w = normalize(full, bars)
    r = backtest(w, bars, cost_bps)
    metrics = score_returns(r, w)
    scored = r.iloc[WARMUP_DAYS:]

    corr_name, max_corr = None, 0.0
    for other_id, other in _found_returns(paths).items():
        joined = pd.concat([scored, other], axis=1, join="inner").dropna()
        if len(joined) > 20 and joined.iloc[:, 0].std() > 0 and joined.iloc[:, 1].std() > 0:
            c = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
            if abs(c) > abs(max_corr):
                corr_name, max_corr = other_id, c

    trials = [row["sr_daily"] for row in prior if row.get("status") == "scored"]
    trials.append(metrics["sr_daily"])

    failed = []
    if metrics["mean_fold_sharpe"] < PASS_MEAN_FOLD_SHARPE:
        failed.append(f"mean_fold_sharpe {metrics['mean_fold_sharpe']} < {PASS_MEAN_FOLD_SHARPE}")
    if metrics["positive_folds"] < PASS_POSITIVE_FOLDS:
        failed.append(f"positive_folds {metrics['positive_folds']} < {PASS_POSITIVE_FOLDS}")
    if abs(max_corr) >= MAX_ABS_CORR:
        failed.append(f"corr {max_corr:.2f} with {corr_name} >= {MAX_ABS_CORR}")

    record |= {
        "status": "scored",
        **metrics,
        "max_corr": round(max_corr, 3),
        "max_corr_with": corr_name,
        "n_trials": len(trials),
        "dsr": round(deflated_sharpe(scored, trials), 4),
        "passed": not failed,
        "failed_gates": failed,
    }

    if record["passed"]:
        paths.found.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(paths.strategy, paths.found / f"{attempt_id}.py")
        (paths.found / f"{attempt_id}.json").write_text(json.dumps(record, indent=2) + "\n")
        scored.to_frame("ret").to_parquet(paths.found / f"{attempt_id}.returns.parquet")

    _append(paths, record)
    return record
