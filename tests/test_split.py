import json

import pandas as pd
import pytest

from lodestar.data.store import freeze_split, read_split, split_bars
from lodestar.paths import Paths


def test_freeze_split_writes_18_months_back(tmp_path):
    paths = Paths.at(tmp_path)
    start = freeze_split(paths, pd.Timestamp("2026-10-20"))
    assert start == pd.Timestamp("2025-04-20")
    assert json.loads(paths.split_json.read_text())["holdout_start"] == "2025-04-20"


def test_freeze_split_is_frozen(tmp_path):
    paths = Paths.at(tmp_path)
    first = freeze_split(paths, pd.Timestamp("2026-10-20"))
    again = freeze_split(paths, pd.Timestamp("2027-06-01"))
    assert again == first
    assert read_split(paths) == first


def test_read_split_requires_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_split(Paths.at(tmp_path))


def test_split_bars_has_no_overlap(bars):
    start = bars.index[1500]
    research, holdout = split_bars(bars, start)
    assert research.index.max() < start
    assert holdout.index.min() == start
    assert len(research.index) + len(holdout.index) == len(bars.index)
