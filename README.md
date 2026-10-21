# Lodestar

An AI-native research fund. A Claude Code agent proposes daily trading strategies on
~40 liquid US ETFs. A locked harness scores each one honestly after costs.
Strategies that survive a one-time holdout check are paper traded on Alpaca, and
the ledger is committed to git every day.

```
 research/program.md ──► claude -p (headless) ──► research/strategy.py
                                  ▲                        │
                     notes.md,    │                        ▼
                     results.jsonl│              lodestar evaluate  (locked harness)
                                  │                        │
                                  └──── score, logged ◄────┤
                                                           ▼ pass gate
                                                   research/found/
                                                           │  lodestar promote (human, once)
                                                           ▼
                                                   promoted.json ──► lodestar paper ──► Alpaca paper
                                                                                         │
                                                                         paper/ledger/ ◄─┘ (git = track record)
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env          # add your Alpaca *paper* API key and secret
.venv/bin/pytest -q           # runs offline on synthetic data
.venv/bin/python -m lodestar fetch
```

`fetch` downloads split- and dividend-adjusted daily bars from 2016 on, using
Alpaca's free plan. The first fetch freezes the holdout start (the last 18 months)
in `data/split.json`, and it never moves after that. The market data itself is
gitignored and never redistributed.

## Run the research loop

```bash
scripts/loop.sh 10                         # 10 sessions, each up to 3 evaluations
.venv/bin/python -m lodestar board         # leaderboard
```

Each session is a fresh `claude -p` call driven by `research/program.md`. The
agent reads its own journal (`research/notes.md`) and the result log, writes one
idea into `research/strategy.py`, scores it, and records what it learned.
`loop.sh` commits after every session, so `git log research/` shows the full
research history. Set `LODESTAR_MODEL` to choose a model.

## Promote and paper trade

```bash
.venv/bin/python -m lodestar promote 0042-some-strategy   # one look at the holdout, ever
.venv/bin/python -m lodestar paper --dry-run              # see the orders it would send
.venv/bin/python -m lodestar paper                        # send market-on-open orders
```

To trade every weekday without your laptop, add `ALPACA_API_KEY` and
`ALPACA_SECRET_KEY` as repository secrets. The `paper` workflow then runs at
12:30 UTC, before the US open, and commits `paper/ledger/YYYY-MM-DD.json`.
Approved strategies are combined with equal weights in one paper account.

## Why the numbers can be trusted

| Risk | Guard |
|---|---|
| Lookahead bias | Every strategy is re-run on history cut off at random dates. If any past weight changes, it's rejected. |
| Unrealistic fills | Decide after the close, trade at the next open, and pay 5 bps on every unit of turnover. |
| Overfitting by many tries | Every attempt is logged. Results report the deflated Sharpe ratio (Bailey & López de Prado), which accounts for the number of trials. |
| Peeking at the test set | The last 18 months are a holdout. `evaluate` never loads it, the agent can't read it, and `promote` uses it once per strategy. |
| One lucky period | The score is the mean Sharpe across 6 walk-forward folds, and at least 4 must be positive. |
| Ten copies of one idea | A new strategy must have an absolute correlation below 0.7 with every strategy already found. |
| Agent edits the rules | The harness is SHA-256 manifested and `evaluate` refuses to run if it changed. The agent's tool policy (`scripts/agent-settings.json`) only lets it edit `strategy.py` and `notes.md` and run `evaluate`/`board`. `loop.sh` stops if anything else changes. |
| Survivorship bias | v1 trades a fixed ETF list. Single stocks will need point-in-time index membership (phase 2). |

Strategy code is AST-checked (numpy and pandas only, no file, network or OS access)
and runs in a child process that only receives research data, with a 60-second
timeout. This is defense in depth, not a security boundary.

## Layout

```
lodestar/data       universe, Alpaca fetcher, Parquet store, frozen split
lodestar/harness    backtest, metrics, folds, lookahead, sandbox, integrity, evaluate, promote
lodestar/paper      rebalance planner, ledger, Alpaca paper broker
research/           the agent's workspace (program, strategy, notes, results, found)
scripts/loop.sh     the autoresearch loop
docs/superpowers/   design spec and implementation plan
```

After editing anything under `lodestar/` yourself, run
`.venv/bin/python -m lodestar rehash`. A test fails until you do.

This is research software trading a paper account. It is not investment advice.
