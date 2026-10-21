import json
import textwrap

import pandas as pd
import pytest

from lodestar.data.store import save_bars
from lodestar.harness.evaluate import IntegrityError, evaluate
from lodestar.paths import Paths
from tests.conftest import make_bars

LONG_TREND = '''
import pandas as pd

def weights(bars):
    w = pd.DataFrame(0.0, index=bars.index, columns=bars.symbols)
    w["{sym}"] = 1.0
    return w
'''

PEEKS = '''
def weights(bars):
    return (bars.close.shift(-1) > bars.close).astype(float) * 0.25
'''

RAISES = '''
def weights(bars):
    raise RuntimeError("bad idea")
'''


@pytest.fixture
def paths(tmp_path):
    p = Paths.at(tmp_path)
    # AAA trends hard (passes), others are noise.
    bars = make_bars(2000, symbols=("AAA", "BBB", "CCC", "DDD"), seed=3,
                     drift=[0.0015, 0.0, 0.0, 0.0])
    save_bars(bars, p.research_bars)
    p.strategy.parent.mkdir(parents=True)
    return p


def run(paths, source, name="test", **kw):
    paths.strategy.write_text(textwrap.dedent(source))
    return evaluate(paths, name, "hypothesis text", check_integrity=False, **kw)


def rows(paths):
    return [json.loads(line) for line in paths.results.read_text().splitlines()]


def test_scored_attempt_is_logged_and_snapshotted(paths):
    rec = run(paths, LONG_TREND.format(sym="AAA"), name="Long AAA!")
    assert rec["status"] == "scored"
    assert rec["id"] == "0001-long-aaa"
    for key in ("mean_fold_sharpe", "fold_sharpes", "positive_folds", "sharpe", "cagr",
                "max_drawdown", "annual_turnover", "dsr", "max_corr", "passed", "sr_daily"):
        assert key in rec
    assert len(rec["fold_sharpes"]) == 6
    assert (paths.attempts / "0001-long-aaa.py").read_text() == paths.strategy.read_text()
    assert rows(paths)[0]["id"] == "0001-long-aaa"


def test_passing_strategy_lands_in_found(paths):
    rec = run(paths, LONG_TREND.format(sym="AAA"))
    assert rec["passed"], rec
    assert (paths.found / f"{rec['id']}.py").exists()
    assert json.loads((paths.found / f"{rec['id']}.json").read_text())["id"] == rec["id"]
    r = pd.read_parquet(paths.found / f"{rec['id']}.returns.parquet")
    assert len(r) > 1000


def test_duplicate_of_found_strategy_fails_correlation_gate(paths):
    first = run(paths, LONG_TREND.format(sym="AAA"), name="one")
    second = run(paths, LONG_TREND.format(sym="AAA"), name="two")
    assert first["passed"]
    assert second["max_corr"] == pytest.approx(1.0)
    assert not second["passed"]
    assert any("corr" in f for f in second["failed_gates"])


def test_noise_strategy_does_not_pass(paths):
    rec = run(paths, LONG_TREND.format(sym="BBB"))
    assert rec["status"] == "scored" and not rec["passed"]


def test_lookahead_is_rejected(paths):
    rec = run(paths, PEEKS)
    assert rec["status"] == "rejected"
    assert "lookahead" in rec["reason"]
    assert not paths.found.exists() or not any(paths.found.iterdir())


def test_exception_is_an_error_row(paths):
    rec = run(paths, RAISES)
    assert rec["status"] == "error"
    assert "bad idea" in rec["reason"]


def test_dsr_counts_prior_scored_trials_only(paths):
    run(paths, RAISES)
    run(paths, LONG_TREND.format(sym="BBB"), name="b")
    rec = run(paths, LONG_TREND.format(sym="CCC"), name="c")
    assert rec["n_trials"] == 2


def test_integrity_failure_refuses_to_score(paths, tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "x.py").write_text("")
    paths.strategy.write_text(LONG_TREND.format(sym="AAA"))
    with pytest.raises(IntegrityError):
        evaluate(paths, "x", "h", pkg_dir=pkg)
    assert not paths.results.exists()


from lodestar.harness.evaluate import session_budget_error  # noqa: E402


def test_session_budget_unlimited_without_env(paths):
    assert session_budget_error(paths, {}) is None


def test_session_budget_counts_attempts_since_session_start(paths):
    env = {"LODESTAR_SESSION_START": "0", "LODESTAR_MAX_EVALS": "2"}
    assert session_budget_error(paths, env) is None
    run(paths, RAISES, name="a")
    assert session_budget_error(paths, env) is None
    run(paths, RAISES, name="b")
    msg = session_budget_error(paths, env)
    assert msg and "limit" in msg
    # a new session starting after those two rows has a fresh budget
    assert session_budget_error(paths, {**env, "LODESTAR_SESSION_START": "2"}) is None
