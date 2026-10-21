"""Download adjusted daily bars from Alpaca and store the research/holdout split.

Free Alpaca accounts may query the consolidated (SIP) feed for anything older than
15 minutes. We only ask for completed sessions, so SIP works on the free plan.
"""
from __future__ import annotations

import os

import pandas as pd

from lodestar.data.store import Bars, freeze_split, save_bars, split_bars
from lodestar.data.universe import UNIVERSE

START = "2016-01-01"
ET = "America/New_York"


def completed_session_end(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """One second before today's ET midnight, so today's partial bar is never included."""
    now = pd.Timestamp.now(tz="UTC") if now is None else now
    today_et = now.tz_convert(ET).normalize()
    return today_et - pd.Timedelta(seconds=1)


def bars_from_alpaca_df(df: pd.DataFrame) -> Bars:
    long = df.reset_index()
    long["date"] = long["timestamp"].dt.tz_convert(ET).dt.tz_localize(None).dt.normalize()
    return Bars.from_long(long[["date", "symbol", *Bars.FIELDS]])


def make_client():
    from alpaca.data.historical import StockHistoricalDataClient
    from dotenv import load_dotenv

    load_dotenv()
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("ALPACA_API_KEY / ALPACA_SECRET_KEY are not set (copy .env.example to .env).")
    return StockHistoricalDataClient(key, secret)


def fetch_bars(symbols=UNIVERSE, start=START, end=None, client=None) -> Bars:
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = client or make_client()
    req = StockBarsRequest(
        symbol_or_symbols=list(symbols),
        timeframe=TimeFrame.Day,
        start=pd.Timestamp(start, tz=ET).to_pydatetime(),
        end=(end or completed_session_end()).to_pydatetime(),
        adjustment=Adjustment.ALL,
        feed=DataFeed.SIP,
    )
    df = client.get_stock_bars(req).df
    if df.empty:
        raise RuntimeError("Alpaca returned no bars.")
    bars = bars_from_alpaca_df(df)
    missing = sorted(set(symbols) - set(bars.symbols))
    if missing:
        raise RuntimeError(f"No bars for: {', '.join(missing)}")
    return bars


def fetch_and_store(paths, client=None) -> dict:
    bars = fetch_bars(client=client)
    holdout_start = freeze_split(paths, bars.index[-1])
    research, holdout = split_bars(bars, holdout_start)
    save_bars(research, paths.research_bars)
    save_bars(holdout, paths.holdout_bars)
    return {
        "symbols": len(bars.symbols),
        "research": f"{research.index[0].date()} .. {research.index[-1].date()} ({len(research.index)} days)",
        "holdout": f"{holdout.index[0].date()} .. {holdout.index[-1].date()} ({len(holdout.index)} days)",
    }
