from pathlib import Path

from lodestar.paths import DEFAULT, Paths


def test_layout_is_relative_to_root(tmp_path):
    p = Paths.at(tmp_path)
    assert p.research_bars == tmp_path / "data" / "research" / "bars.parquet"
    assert p.holdout_bars == tmp_path / "data" / "holdout" / "bars.parquet"
    assert p.split_json == tmp_path / "data" / "split.json"
    assert p.strategy == tmp_path / "research" / "strategy.py"
    assert p.notes == tmp_path / "research" / "notes.md"
    assert p.results == tmp_path / "research" / "results.jsonl"
    assert p.attempts == tmp_path / "research" / "attempts"
    assert p.found == tmp_path / "research" / "found"
    assert p.promoted == tmp_path / "research" / "promoted.json"
    assert p.ledger == tmp_path / "paper" / "ledger"


def test_default_root_is_repo():
    assert (DEFAULT.root / "pyproject.toml").exists()
    assert DEFAULT.root == Path(__file__).resolve().parents[1]
