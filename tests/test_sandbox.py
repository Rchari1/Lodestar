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
])
def test_rejects_io_and_escape_hatches(snippet):
    assert scan(GOOD + "\n" + snippet + "\n"), snippet


def test_requires_weights_function():
    problems = scan("import numpy as np\n")
    assert any("weights" in p for p in problems)


def test_syntax_error_is_reported():
    assert any("syntax" in p.lower() for p in scan("def weights(:\n"))
