import pandas as pd

from lodestar.data.store import Bars, concat_bars, load_bars, save_bars
from tests.conftest import make_bars


def test_long_round_trip(bars):
    back = Bars.from_long(bars.to_long())
    pd.testing.assert_frame_equal(back.close, bars.close, check_freq=False)
    pd.testing.assert_frame_equal(back.volume, bars.volume, check_freq=False)
    assert back.symbols == bars.symbols


def test_parquet_round_trip(tmp_path, bars):
    path = tmp_path / "x" / "bars.parquet"
    save_bars(bars, path)
    back = load_bars(path)
    pd.testing.assert_frame_equal(back.open, bars.open, check_freq=False)


def test_truncate_keeps_rows_up_to_and_including_end(bars):
    end = bars.index[100]
    t = bars.truncate(end)
    assert t.index[-1] == end
    assert len(t.index) == 101
    assert t.close.shape[1] == bars.close.shape[1]


def test_concat_orders_and_dedupes():
    a = make_bars(50, seed=1)
    full = make_bars(80, seed=1)
    b = Bars(*(getattr(full, f).iloc[40:] for f in Bars.FIELDS))
    c = concat_bars(a, b)
    assert c.index.is_monotonic_increasing
    assert c.index.is_unique
    assert len(c.index) == 80
