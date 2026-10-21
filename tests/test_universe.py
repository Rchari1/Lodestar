from lodestar.data.universe import UNIVERSE


def test_universe_shape():
    assert len(UNIVERSE) == len(set(UNIVERSE))
    assert 40 <= len(UNIVERSE) <= 45
    assert all(s.isupper() and s.isalpha() for s in UNIVERSE)


def test_core_benchmarks_present():
    for s in ("SPY", "TLT", "GLD"):
        assert s in UNIVERSE
