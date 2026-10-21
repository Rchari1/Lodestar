"""Where everything lives. Every function takes a Paths so tests can use a temp dir."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path

    @classmethod
    def at(cls, root: str | Path) -> "Paths":
        return cls(Path(root).resolve())

    # data
    @property
    def research_bars(self) -> Path:
        return self.root / "data" / "research" / "bars.parquet"

    @property
    def holdout_bars(self) -> Path:
        return self.root / "data" / "holdout" / "bars.parquet"

    @property
    def split_json(self) -> Path:
        return self.root / "data" / "split.json"

    # research workspace
    @property
    def research_dir(self) -> Path:
        return self.root / "research"

    @property
    def strategy(self) -> Path:
        return self.research_dir / "strategy.py"

    @property
    def notes(self) -> Path:
        return self.research_dir / "notes.md"

    @property
    def results(self) -> Path:
        return self.research_dir / "results.jsonl"

    @property
    def attempts(self) -> Path:
        return self.research_dir / "attempts"

    @property
    def found(self) -> Path:
        return self.research_dir / "found"

    @property
    def promoted(self) -> Path:
        return self.research_dir / "promoted.json"

    # paper trading
    @property
    def ledger(self) -> Path:
        return self.root / "paper" / "ledger"


DEFAULT = Paths.at(Path(__file__).resolve().parents[1])
