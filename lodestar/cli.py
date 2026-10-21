"""python -m lodestar <command>"""
from __future__ import annotations

import argparse
import json
import sys

from lodestar.paths import DEFAULT


def format_record(rec: dict) -> str:
    head = f"[{rec['id']}]"
    if rec["status"] != "scored":
        reason = rec.get("reason", "").strip().splitlines()
        return f"{head} {rec['status'].upper()}: {reason[-1] if reason else ''}"
    verdict = "PASSED" if rec["passed"] else "failed"
    folds = ", ".join(f"{x:+.2f}" for x in rec["fold_sharpes"])
    line = (f"{head} {verdict}  mean_fold_sharpe={rec['mean_fold_sharpe']:.2f} "
            f"folds=[{folds}] positive={rec['positive_folds']}/{len(rec['fold_sharpes'])} "
            f"sharpe={rec['sharpe']:.2f} cagr={rec['cagr']:.1%} maxdd={rec['max_drawdown']:.1%} "
            f"turnover={rec['annual_turnover']:.1f}x/yr dsr={rec['dsr']:.2f} "
            f"max_corr={rec['max_corr']:+.2f}")
    if rec.get("max_corr_with"):
        line += f" ({rec['max_corr_with']})"
    if rec["failed_gates"]:
        line += "  gates: " + "; ".join(rec["failed_gates"])
    return line


def cmd_fetch(args) -> int:
    from lodestar.data.fetch import fetch_and_store
    for k, v in fetch_and_store(DEFAULT).items():
        print(f"{k:>9}: {v}")
    return 0


def cmd_evaluate(args) -> int:
    import os

    from lodestar.harness.evaluate import IntegrityError, evaluate, session_budget_error
    over = session_budget_error(DEFAULT, os.environ)
    if over:
        print(f"REFUSED: {over}", file=sys.stderr)
        return 3
    try:
        rec = evaluate(DEFAULT, args.name, args.hypothesis)
    except IntegrityError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    print(format_record(rec))
    if rec.get("passed"):
        print(f"saved to research/found/{rec['id']}.py")
    return 0


def cmd_promote(args) -> int:
    from lodestar.harness.promote import promote
    if not args.yes:
        answer = input(f"Use the one-time holdout look for {args.id}? [y/N] ")
        if answer.strip().lower() != "y":
            print("aborted")
            return 1
    rec = promote(DEFAULT, args.id, threshold=args.threshold)
    print(json.dumps(rec, indent=2))
    print("APPROVED for paper trading" if rec["approved"] else "not approved")
    return 0


def cmd_paper(args) -> int:
    import pandas as pd

    from lodestar.data.fetch import fetch_bars
    from lodestar.paper.alpaca_broker import AlpacaPaperBroker
    from lodestar.paper.trader import run_paper

    today = pd.Timestamp.now(tz="America/New_York").date()
    out = run_paper(DEFAULT, AlpacaPaperBroker(), fetch_bars, today, dry_run=args.dry_run)
    print(json.dumps(out, indent=2))
    return 0


def cmd_rehash(args) -> int:
    from lodestar.harness.integrity import write_manifest
    print(f"wrote {write_manifest()}")
    return 0


def cmd_board(args) -> int:
    from lodestar.harness.evaluate import read_results
    rows = [r for r in read_results(DEFAULT) if r.get("status") == "scored"]
    rows.sort(key=lambda r: r["mean_fold_sharpe"], reverse=True)
    total = len(read_results(DEFAULT))
    print(f"{total} attempts, {len(rows)} scored, {sum(r['passed'] for r in rows)} passed\n")
    for r in rows[: args.top]:
        print(format_record(r))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lodestar")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch", help="download daily bars from Alpaca and write the research/holdout split")

    e = sub.add_parser("evaluate", help="score research/strategy.py on the research period")
    e.add_argument("--name", required=True, help="short name for this attempt")
    e.add_argument("--hypothesis", required=True, help="one line: why this should work")

    pr = sub.add_parser("promote", help="(human only) one-time holdout check of a found strategy")
    pr.add_argument("id")
    pr.add_argument("--threshold", type=float, default=0.3)
    pr.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    pa = sub.add_parser("paper", help="rebalance the Alpaca paper account (run before the open)")
    pa.add_argument("--dry-run", action="store_true")

    sub.add_parser("rehash", help="(human only) regenerate the harness integrity manifest")

    b = sub.add_parser("board", help="leaderboard of scored attempts")
    b.add_argument("--top", type=int, default=15)
    return p


COMMANDS = {"fetch": cmd_fetch, "evaluate": cmd_evaluate, "promote": cmd_promote,
            "paper": cmd_paper, "rehash": cmd_rehash, "board": cmd_board}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)
