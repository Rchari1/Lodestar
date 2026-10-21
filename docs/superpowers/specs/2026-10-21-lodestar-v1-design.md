# Lodestar v1 — Design

An AI-native research fund: a headless Claude Code agent proposes daily ETF
strategies, a locked harness scores them honestly, and strategies that pass a
one-time holdout check are paper traded on Alpaca. The paper ledger, committed
to git every day, is the track record.

## Decisions

| Topic | Choice |
|---|---|
| Asset class | US-listed ETFs (single stocks are phase 2) |
| Frequency | Daily bars; decide after close *t*, execute at open *t+1* |
| Data + broker | Alpaca (free plan): historical bars and the paper trading account |
| Research agent | Claude Code headless (`claude -p`), run in a loop |
| Holdout | The last 18 months of data at first fetch, frozen in `data/split.json` |
| Costs | 5 bps per unit of turnover (deliberately pessimistic for ETFs) |

## Layout

```
lodestar/
  data/universe.py      the ~40 ETF tickers
  data/store.py         Bars container, Parquet load/save, research/holdout split
  data/fetch.py         Alpaca → Parquet (adjusted daily bars since 2016-01-01)
  harness/backtest.py   weights → daily net returns
  harness/metrics.py    Sharpe, CAGR, drawdown, turnover, deflated Sharpe
  harness/splits.py     walk-forward fold boundaries
  harness/lookahead.py  truncation test for use of future data
  harness/sandbox.py    AST checks + subprocess run with a timeout
  harness/integrity.py  SHA-256 manifest of harness files
  harness/evaluate.py   scores research/strategy.py, logs the attempt
  harness/promote.py    one-time holdout evaluation (human only)
  paper/trader.py       daily rebalance on Alpaca paper
  cli.py                `python -m lodestar {fetch,evaluate,promote,paper,rehash}`
research/
  program.md            the agent's standing instructions
  strategy.py           the ONLY code file the agent edits
  notes.md              the agent's journal across sessions (agent-editable)
  results.jsonl         every attempt, appended by evaluate
  attempts/<id>.py      source snapshot of every attempt
  found/<id>.py,.json   attempts that passed the research gate
  promoted.json         holdout results, written by promote
paper/ledger/           one JSON file per trading day
scripts/loop.sh         runs N agent sessions, commits after each
.github/workflows/paper.yml   weekday paper run, commits the ledger
```

## Strategy contract

```python
def weights(bars: Bars) -> pd.DataFrame: ...
```

`Bars` has wide DataFrames `open, high, low, close, volume`, indexed by date
with one column per ticker. The function returns target weights indexed by
the same dates. A row for date *t* may use data up to and including *t*'s
close. Before the backtest, the harness reindexes the output to the bars,
fills NaN with 0, zeroes tickers with no price, and scales any row whose
gross exposure (sum of |w|) exceeds 1.0 down to 1.0.

The strategy must be deterministic. Allowed imports are numpy, pandas, math,
statistics, itertools, functools, collections, dataclasses and typing. File,
network and process access is rejected before the code runs (see Sandbox).

## Backtest

The weight decided at *t* is held from open *t+1* to open *t+2*:
`r_port[t+1] = Σ w[t] · (open[t+2]/open[t+1] − 1) − cost · Σ|w[t] − w[t−1]|`.
Positions are rebalanced to target every day, so there's no drift between
rebalances.

## Scoring (research period only)

- The research period splits into 6 equal, contiguous walk-forward folds. The
  first 252 trading days are warm-up and aren't scored.
- The score is the mean annualized Sharpe across folds. Also reported: the
  minimum fold Sharpe, the number of positive folds, full-period Sharpe,
  CAGR, max drawdown, annual turnover and the deflated Sharpe ratio (DSR).
- **Pass gate:** mean fold Sharpe ≥ 0.7, at least 4 of 6 folds positive, a
  lookahead check pass, and |correlation| < 0.7 between this strategy's daily
  returns and every strategy already in `found/`.
- **DSR** follows Bailey & López de Prado (2014). The number of trials and
  the variance of their Sharpes come from every scored row in `results.jsonl`.
  DSR is reported but not used as a gate in v1, because early in a run there
  are too few trials for it to mean much.

## Lookahead check

Run `weights` on the full research data, then again on data truncated at 5
seeded random cutoffs. The weights for every date up to each cutoff must match
the full run to within 1e-9. Any mismatch rejects the attempt.

## Sandbox (defense in depth, not a security boundary)

1. AST scan of `strategy.py`: only allow-listed imports. Reject the names
   `open, exec, eval, compile, __import__, globals, locals, vars, input,
   breakpoint`, any dunder attribute, and file I/O attributes (`read_*`, `to_csv`,
   `to_parquet`, `to_pickle`, `to_json`, `to_sql`, `to_excel`, `to_hdf`,
   `to_feather`, `tofile`, `fromfile`, `load`, `save`, `savez`, `loadtxt`,
   `savetxt`, `genfromtxt`).
2. The strategy runs in a child process, which only ever receives research
   data, with a 60-second timeout.
3. The evaluate process never loads the holdout file.

## Agent isolation

`scripts/loop.sh` runs `claude -p` with:
- `--tools Read,Glob,Grep,Edit,Write,Bash`
- `--allowedTools` limited to reading the repo, `Edit`/`Write` on
  `research/strategy.py` and `research/notes.md` only, and
  `Bash(.venv/bin/python -m lodestar evaluate:*)`
- `--permission-mode dontAsk`, so everything else is denied without a prompt
- `.claude/settings.json` deny rules for `data/holdout/**`, `lodestar/**` edits,
  `.env`, and the `promote` and `paper` commands

`harness/MANIFEST.sha256` lists hashes of `lodestar/**/*.py`. `evaluate`
refuses to run if any hash differs, and a test keeps the manifest current.
`python -m lodestar rehash` regenerates it and is for humans only.

## Session flow (one `claude -p` call)

1. Read `program.md` (passed as the prompt), `notes.md`, the last 30 rows of
   `results.jsonl`, and `found/`.
2. Write a new hypothesis into `strategy.py`, then run
   `evaluate --name <slug> --hypothesis "<one line>"`. Up to 3 evaluations per
   session, each of which counts as a trial.
3. Append what was learned to `notes.md`, then exit. `loop.sh` commits
   `research/` with the message `research: <slug> score=<x>`.

## Promotion (human only)

`python -m lodestar promote <id>` evaluates a strategy in `found/` exactly once
on the holdout (with research data as warm-up history). The holdout Sharpe and
other metrics go into `research/promoted.json`. It's `approved` if holdout
Sharpe ≥ 0.3. A second attempt on the same id is refused.

## Paper trading

`python -m lodestar paper [--dry-run]`:
1. Skips if today isn't a trading day, using the Alpaca clock and calendar.
2. Fetches fresh bars through the previous close.
3. Computes the latest weights for each approved strategy and averages them
   with equal weight per strategy.
4. Target shares = trunc(weight × equity / last close), as whole shares,
   either long or short. It submits the difference from current positions as
   market-on-open (`OPG`) orders, sells first. That matches the backtest's
   open execution.
5. Writes `paper/ledger/YYYY-MM-DD.json` with equity, the per-strategy
   weights, the combined targets, current positions and the orders sent.

A GitHub Actions workflow runs it on weekdays at 12:30 UTC (before the US
open in both EST and EDT) using repo secrets, and commits the ledger.

## Errors

If strategy code raises, returns the wrong shape, returns NaN everywhere,
times out or fails the sandbox scan, the result is a `status: "error"` row in
`results.jsonl` with the message. It doesn't count as a scored trial for DSR.
Data fetch failures stop the command with a clear error. The paper trader
never sends orders after a failed step.

## Testing

pytest, test-first, on synthetic data (no network access):
- cost math and the open-to-open execution timing
- the folds never touch the holdout, and the split is frozen
- the lookahead check catches `close.shift(-1)`
- sandbox rejects `open()`, `import os` and `pd.read_parquet`
- an edited harness file trips the integrity check
- DSR matches a hand-computed value
- paper target-share math and order diffs (with a fake broker)

## Out of scope for v1

Single stocks and point-in-time index membership, a dashboard, parallel
agents, intraday data, and live (real-money) trading.
