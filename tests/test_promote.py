import json

import pytest

from lodestar.data.store import freeze_split, save_bars, split_bars
from lodestar.harness.promote import AlreadyPromoted, promote
from lodestar.paths import Paths
from tests.conftest import make_bars

LONG_AAA = '''
import pandas as pd

def weights(bars):
    w = pd.DataFrame(0.0, index=bars.index, columns=bars.symbols)
    w["AAA"] = 1.0
    return w
'''


@pytest.fixture
def paths(tmp_path):
    p = Paths.at(tmp_path)
    bars = make_bars(2400, seed=5, drift=[0.0015, 0.0, 0.0, 0.0])
    start = freeze_split(p, bars.index[-1])
    research, holdout = split_bars(bars, start)
    save_bars(research, p.research_bars)
    save_bars(holdout, p.holdout_bars)
    p.found.mkdir(parents=True)
    (p.found / "0007-long-aaa.py").write_text(LONG_AAA)
    return p


def test_promote_records_holdout_metrics(paths):
    rec = promote(paths, "0007-long-aaa")
    assert rec["approved"] is True
    assert rec["holdout_days"] > 300
    assert rec["holdout_start"] == json.loads(paths.split_json.read_text())["holdout_start"]
    saved = json.loads(paths.promoted.read_text())
    assert saved["0007-long-aaa"]["holdout_sharpe"] == rec["holdout_sharpe"]


def test_holdout_is_used_once(paths):
    promote(paths, "0007-long-aaa")
    with pytest.raises(AlreadyPromoted):
        promote(paths, "0007-long-aaa")


def test_unknown_id(paths):
    with pytest.raises(FileNotFoundError):
        promote(paths, "9999-nope")


def test_threshold_decides_approval(paths):
    rec = promote(paths, "0007-long-aaa", threshold=99.0)
    assert rec["approved"] is False
