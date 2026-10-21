import pytest

from lodestar.cli import build_parser, format_record

SUBCOMMANDS = ["fetch", "evaluate", "promote", "paper", "rehash", "board"]


@pytest.mark.parametrize("cmd", SUBCOMMANDS)
def test_help_parses(cmd, capsys):
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args([cmd, "--help"])
    assert e.value.code == 0


def test_evaluate_requires_name_and_hypothesis():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["evaluate"])


def test_format_scored_record():
    rec = {"id": "0003-x", "status": "scored", "mean_fold_sharpe": 0.82,
           "fold_sharpes": [1.0, 0.5, 0.9, -0.1, 1.2, 0.4], "positive_folds": 5, "sharpe": 0.9,
           "cagr": 0.071, "max_drawdown": -0.123, "annual_turnover": 4.2, "dsr": 0.71,
           "max_corr": 0.12, "max_corr_with": "0001-y", "passed": True, "failed_gates": []}
    line = format_record(rec)
    assert line.startswith("[0003-x] PASSED")
    assert "mean_fold_sharpe=0.82" in line and "positive=5/6" in line


def test_format_error_record():
    line = format_record({"id": "0004-z", "status": "error", "reason": "Traceback...\nValueError: boom"})
    assert "ERROR" in line and "boom" in line
