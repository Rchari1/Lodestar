"""Keep strategy code to pure computation on the bars it's given.

This is defense in depth, not a security boundary: an AST allow-list stops the
obvious ways strategy code could read the holdout or write files, and the code runs
in a child process that only ever receives research data.
"""
from __future__ import annotations

import ast
import multiprocessing as mp
import time
import traceback
from pathlib import Path

import pandas as pd

ALLOWED_IMPORTS = {
    "numpy", "pandas", "math", "statistics", "itertools", "functools",
    "collections", "dataclasses", "typing", "__future__",
}
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
    "input", "breakpoint", "getattr", "setattr", "delattr", "memoryview", "exit", "quit",
}
FORBIDDEN_ATTRS = {
    "to_csv", "to_parquet", "to_pickle", "to_json", "to_sql", "to_excel", "to_hdf",
    "to_feather", "to_stata", "to_orc", "to_html", "to_latex", "to_markdown", "to_xml",
    "to_clipboard", "tofile", "fromfile", "load", "save", "savez", "savez_compressed",
    "loadtxt", "savetxt", "genfromtxt", "memmap", "io", "lib", "ctypeslib", "testing",
    "f2py", "distutils", "to_string", "fromregex", "DataSource", "HDFStore", "ExcelFile",
    "ExcelWriter", "api",
}


class StrategyError(Exception):
    """The strategy failed to scan, run, or return valid weights."""


def _module_allowed(name: str) -> bool:
    root, *rest = name.split(".")
    return root in ALLOWED_IMPORTS and not set(rest) & FORBIDDEN_ATTRS


def scan(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"syntax error: {e}"]
    problems: list[str] = []

    def bad(node, msg):
        problems.append(f"line {getattr(node, 'lineno', '?')}: {msg}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _module_allowed(alias.name):
                    bad(node, f"import of '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level or not _module_allowed(mod):
                bad(node, f"import from '{mod}' is not allowed")
            for alias in node.names:
                if alias.name in FORBIDDEN_ATTRS or alias.name in FORBIDDEN_NAMES:
                    bad(node, f"importing '{alias.name}' is not allowed")
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or (node.id.startswith("__") and node.id.endswith("__")):
                bad(node, f"name '{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute):
            a = node.attr
            if a.startswith("__") or a.startswith("read_") or a in FORBIDDEN_ATTRS:
                bad(node, f"attribute '.{a}' is not allowed")

    if not any(isinstance(n, ast.FunctionDef) and n.name == "weights" for n in tree.body):
        problems.append("strategy must define a top-level function `weights(bars)`")
    return problems


# --- running ------------------------------------------------------------------

TIMEOUT_S = 60


def _child(source: str, filename: str, bars, cutoffs, conn) -> None:
    try:
        namespace: dict = {"__name__": "strategy"}
        exec(compile(source, filename, "exec"), namespace)
        fn = namespace["weights"]
        full = fn(bars)
        cuts = {c: fn(bars.truncate(c)) for c in cutoffs}
        conn.send(("ok", full, cuts))
    except BaseException:  # noqa: BLE001 - report everything to the parent
        conn.send(("error", traceback.format_exc(limit=5), None))
    finally:
        conn.close()


def _wait_for_result(conn, proc, timeout: float) -> None:
    """Block until the child sends a result. Fail fast if it dies, fail at the timeout if it hangs."""
    deadline = time.monotonic() + timeout
    while not conn.poll(0.1):
        if not proc.is_alive() and not conn.poll(0):
            raise StrategyError(f"strategy process exited (code {proc.exitcode}) without a result")
        if time.monotonic() > deadline:
            raise StrategyError(f"strategy timed out after {timeout:g}s")


def run_strategy(path, bars, cutoffs=(), timeout: float = TIMEOUT_S):
    """Run `weights(bars)` (plus one run per truncation cutoff) in a child process.

    Returns (full_weights, {cutoff: weights}). Raises StrategyError on any failure.
    """
    source = Path(path).read_text()
    problems = scan(source)
    if problems:
        raise StrategyError("; ".join(problems))

    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(source, str(path), bars, list(cutoffs), child), daemon=True)
    proc.start()
    child.close()
    try:
        _wait_for_result(parent, proc, timeout)
        status, full, cuts = parent.recv()
    except EOFError:
        raise StrategyError("strategy process died without a result") from None
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        parent.close()

    if status != "ok":
        raise StrategyError(full)
    for w in [full, *cuts.values()]:
        if not isinstance(w, pd.DataFrame):
            raise StrategyError(f"weights() must return a pandas DataFrame, got {type(w).__name__}")
    if full.reindex(index=bars.index).isna().all().all():
        raise StrategyError("weights() returned only NaN")
    return full, cuts
