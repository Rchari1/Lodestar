import textwrap

import pytest

from lodestar.harness.sandbox import scan

GOOD = textwrap.dedent('''
    import numpy as np
    import pandas as pd
    from collections import OrderedDict

    LOOKBACK = 252

    def weights(bars):
        mom = bars.close / bars.close.shift(LOOKBACK) - 1
        w = (mom > 0).astype(float)
        return w.div(w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
''')


def test_accepts_plain_numpy_pandas_strategy():
    assert scan(GOOD) == []


@pytest.mark.parametrize("snippet", [
    "import os",
    "import subprocess",
    "from pathlib import Path",
    "import pandas.io.parquet",
    "x = open('data/holdout/bars.parquet')",
    "x = pd.read_parquet('data/holdout/bars.parquet')",
    "bars.close.to_csv('leak.csv')",
    "np.save('x', 1)",
    "y = bars.__class__",
    "eval('1')",
    "f = getattr(pd, 'read_csv')",
    "__import__('os')",
    "s = pd.HDFStore('data/holdout/bars.h5')",
    "x = pd.ExcelFile('x.xlsx')",
    "bars.close.to_string(buf='leak.txt')",
    "x = np.fromregex('f', 'r', float)",
    "x = np.DataSource()",
])
def test_rejects_io_and_escape_hatches(snippet):
    assert scan(GOOD + "\n" + snippet + "\n"), snippet


def test_requires_weights_function():
    problems = scan("import numpy as np\n")
    assert any("weights" in p for p in problems)


def test_syntax_error_is_reported():
    assert any("syntax" in p.lower() for p in scan("def weights(:\n"))


from lodestar.harness.sandbox import StrategyError, run_strategy  # noqa: E402


def _write(tmp_path, body):
    p = tmp_path / "strategy.py"
    p.write_text(textwrap.dedent(body))
    return p


def test_runs_full_and_truncated(tmp_path, bars):
    p = _write(tmp_path, GOOD)
    cutoffs = [bars.index[400], bars.index[900]]
    full, cuts = run_strategy(p, bars, cutoffs, timeout=60)
    assert full.shape == bars.close.shape
    assert set(cuts) == set(cutoffs)
    assert cuts[cutoffs[0]].index[-1] == cutoffs[0]


def test_exception_becomes_strategy_error(tmp_path, bars):
    p = _write(tmp_path, "def weights(bars):\n    raise ValueError('boom')\n")
    with pytest.raises(StrategyError, match="boom"):
        run_strategy(p, bars)


def test_infinite_loop_is_killed(tmp_path, bars):
    p = _write(tmp_path, "def weights(bars):\n    while True:\n        pass\n")
    with pytest.raises(StrategyError, match="timed out"):
        run_strategy(p, bars, timeout=3)


def test_non_dataframe_is_rejected(tmp_path, bars):
    p = _write(tmp_path, "def weights(bars):\n    return 1.0\n")
    with pytest.raises(StrategyError, match="DataFrame"):
        run_strategy(p, bars)


def test_scan_failure_is_raised_before_running(tmp_path, bars):
    p = _write(tmp_path, "import os\ndef weights(bars):\n    return bars.close * 0\n")
    with pytest.raises(StrategyError, match="not allowed"):
        run_strategy(p, bars)
