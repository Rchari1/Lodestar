"""Daily bars as wide frames (date x symbol), stored on disk as long-format Parquet."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pandas as pd


@dataclass(frozen=True)
class Bars:
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame

    FIELDS: ClassVar[tuple[str, ...]] = ("open", "high", "low", "close", "volume")

    @property
    def index(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def symbols(self) -> list[str]:
        return list(self.close.columns)

    def _map(self, fn) -> "Bars":
        return Bars(*(fn(getattr(self, f)) for f in self.FIELDS))

    def truncate(self, end) -> "Bars":
        """Rows dated on or before `end`."""
        end = pd.Timestamp(end)
        return self._map(lambda df: df.loc[df.index <= end].copy())

    def between(self, start=None, end=None) -> "Bars":
        """Rows with start <= date < end (either side open when None)."""
        def cut(df):
            mask = pd.Series(True, index=df.index)
            if start is not None:
                mask &= df.index >= pd.Timestamp(start)
            if end is not None:
                mask &= df.index < pd.Timestamp(end)
            return df.loc[mask.to_numpy()].copy()
        return self._map(cut)

    def to_long(self) -> pd.DataFrame:
        parts = [getattr(self, f).stack().rename(f) for f in self.FIELDS]
        long = pd.concat(parts, axis=1)
        long.index = long.index.set_names(["date", "symbol"])
        return long.reset_index()

    @classmethod
    def from_long(cls, df: pd.DataFrame) -> "Bars":
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        frames = []
        for f in cls.FIELDS:
            wide = df.pivot(index="date", columns="symbol", values=f).sort_index()
            wide.columns.name = None
            wide.index.name = None
            frames.append(wide.astype(float))
        return cls(*frames)


def concat_bars(a: Bars, b: Bars) -> Bars:
    """Stack two Bars in time; on overlapping dates the later one wins."""
    def join(x, y):
        out = pd.concat([x, y])
        out = out[~out.index.duplicated(keep="last")]
        return out.sort_index()
    return Bars(*(join(getattr(a, f), getattr(b, f)) for f in Bars.FIELDS))


def save_bars(bars: Bars, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bars.to_long().to_parquet(path, index=False)


def load_bars(path: str | Path) -> Bars:
    return Bars.from_long(pd.read_parquet(path))


# --- research / holdout split -------------------------------------------------
# The holdout start is written once, on the first fetch, and never moves. If it
# rolled forward with each fetch, data that had been holdout would leak into research.

HOLDOUT_MONTHS = 18


def freeze_split(paths, last_date, months: int = HOLDOUT_MONTHS) -> pd.Timestamp:
    if paths.split_json.exists():
        return read_split(paths)
    start = (pd.Timestamp(last_date) - pd.DateOffset(months=months)).normalize()
    paths.split_json.parent.mkdir(parents=True, exist_ok=True)
    paths.split_json.write_text(json.dumps(
        {"holdout_start": start.strftime("%Y-%m-%d"), "months": months}, indent=2) + "\n")
    return start


def read_split(paths) -> pd.Timestamp:
    return pd.Timestamp(json.loads(paths.split_json.read_text())["holdout_start"])


def split_bars(bars: Bars, holdout_start) -> tuple[Bars, Bars]:
    return bars.between(end=holdout_start), bars.between(start=holdout_start)
