"""Run the real CLI in a subprocess, the way the research agent does."""
import json
import os
import subprocess
import sys
from pathlib import Path

from lodestar.data.store import save_bars
from lodestar.paths import Paths
from tests.conftest import make_bars

REPO = Path(__file__).resolve().parents[1]


def test_evaluate_via_python_dash_m(tmp_path):
    paths = Paths.at(tmp_path)
    save_bars(make_bars(1800, seed=9), paths.research_bars)
    paths.strategy.parent.mkdir(parents=True)
    paths.strategy.write_text((REPO / "research" / "strategy.py").read_text())

    env = {**os.environ, "LODESTAR_ROOT": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-m", "lodestar", "evaluate", "--name", "baseline", "--hypothesis", "trend"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("[0001-baseline]")
    rows = paths.results.read_text().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["status"] == "scored"
