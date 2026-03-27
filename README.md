# Lodestar

Automated trading application that connects to Robinhood, performs market research using technical and sentiment analysis, and executes trades based on configurable strategies.

> **Disclaimer:** This software is for educational purposes. Automated trading carries significant financial risk. Always start with paper trading. Never risk money you cannot afford to lose.

## Features

- **Robinhood Integration** — Connects via `robin_stocks` with MFA/TOTP support
- **Paper Trading Mode** — Full simulation with no real money at risk
- **Technical Analysis** — RSI, MACD, Bollinger Bands, ADX, Stochastic, ATR, OBV, VWAP, support/resistance
- **Sentiment Analysis** — News headline scraping from Finviz + optional NewsAPI
- **Stock Screener** — Auto-discovers top gainers and most-active tickers
- **Multiple Strategies:**
  - **Momentum** — MACD crossovers + ADX trend strength + RSI confirmation
  - **Mean Reversion** — Bollinger Band bounces + RSI extremes + Stochastic
  - **Sentiment** — News sentiment with technical confirmation
  - **Custom** — Extend `BaseStrategy` to add your own
- **Risk Controls** — Position sizing, daily trade limits, stop-loss, take-profit
- **Web Dashboard** — Real-time portfolio view, trade log, signal history (FastAPI)
- **CLI** — Full-featured command-line interface with Rich formatting
- 
## Project Structure

```
lodestar/
  brokers/          # Brokerage adapters (Robinhood, Paper)
  strategies/       # Trading strategies (momentum, mean reversion, sentiment)
  analysis/         # Technical indicators, sentiment analysis, stock screener
  portfolio/        # Portfolio manager and risk controls
  dashboard/        # FastAPI web dashboard with templates and static assets
  cli/              # Click-based CLI
  models/           # Pydantic data models (Trade, Signal, Position)
  utils/            # Logging helpers
  bot.py            # Core orchestrator
  config.py         # Settings from environment variables
tests/              # Test suite (39 tests)
```

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Robinhood credentials and preferences
```

Key settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ROBINHOOD_USERNAME` | | Your Robinhood email |
| `ROBINHOOD_PASSWORD` | | Your Robinhood password |
| `ROBINHOOD_TOTP_SECRET` | | TOTP secret for automatic MFA |
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `MAX_POSITION_PCT` | `0.05` | Max portfolio % per position |
| `STOP_LOSS_PCT` | `0.03` | Stop-loss threshold |
| `TAKE_PROFIT_PCT` | `0.08` | Take-profit threshold |
| `MAX_DAILY_TRADES` | `20` | Daily trade limit |
| `ENABLED_STRATEGIES` | `momentum,mean_reversion,sentiment` | Active strategies |
| `TRADING_INTERVAL_MINUTES` | `15` | Scan interval |

### 3. Run

```bash
# Paper trading (default)
lodestar run --paper --symbols AAPL,MSFT,TSLA

# Single scan cycle
lodestar scan --symbols AAPL,MSFT,NVDA

# View portfolio
lodestar portfolio

# Launch web dashboard only
lodestar dashboard

# Run bot + dashboard together
lodestar run-all --paper --symbols AAPL,MSFT,TSLA
```

The dashboard runs at `http://localhost:8000` by default.

## Strategies

### Momentum

Detects trends using MACD crossovers confirmed by ADX (trend strength > 25) and RSI. Generates buy signals on bullish crossovers and sell signals on bearish crossovers.

### Mean Reversion

Identifies oversold/overbought conditions using Bollinger Band touches combined with RSI extremes and Stochastic oscillator readings.

### Sentiment

Scrapes financial news headlines, computes sentiment polarity via TextBlob, and confirms with technical indicators (RSI + SMA). Optionally uses NewsAPI for broader coverage.

### Writing a Custom Strategy

```python
from lodestar.strategies.base import BaseStrategy
from lodestar.models.trade import Signal, Side, SignalStrength

class MyStrategy(BaseStrategy):
    name = "my_strategy"

    def evaluate(self, symbol, df):
        # df is a pandas DataFrame with OHLCV + all technical indicators
        latest = df.iloc[-1]
        if latest["rsi"] < 20:
            return Signal(
                symbol=symbol,
                side=Side.BUY,
                strength=SignalStrength.STRONG_BUY,
                strategy=self.name,
                confidence=0.8,
                reason="RSI extremely oversold",
            )
        return None
```

Register it in `lodestar/strategies/__init__.py`:

```python
STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

## Risk Controls

- **Position Sizing** — Each trade is capped at `MAX_POSITION_PCT` of total equity, scaled by signal confidence
- **Daily Trade Limit** — Stops trading after `MAX_DAILY_TRADES` per day
- **Stop-Loss** — Automatically sells positions that drop below `STOP_LOSS_PCT`
- **Take-Profit** — Automatically sells positions that rise above `TAKE_PROFIT_PCT`
- **Cash Buffer** — Keeps a 2% cash reserve to avoid margin calls
- **Live Mode Confirmation** — Requires explicit confirmation before live trading

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard page |
| `GET /api/status` | Bot status, equity, trade counts |
| `GET /api/positions` | Current positions with P&L |
| `GET /api/trades` | Recent trade history |
| `GET /api/signals` | Recent signal log |
| `GET /api/snapshots` | Equity snapshots over time |


## License

Boost Software License 1.0 — see [LICENSE](LICENSE).
