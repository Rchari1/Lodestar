"""Keep strategy code to pure computation on the bars it's given.

This is defense in depth, not a security boundary: an AST allow-list stops the
obvious ways strategy code could read the holdout or write files, and the code runs
in a child process that only ever receives research data.
"""
from __future__ import annotations

import ast

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
    "f2py", "distutils",
}


class StrategyError(Exception):
    """The strategy failed to scan, run, or return valid weights."""


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
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS or alias.name.count(".") and \
                        set(alias.name.split(".")[1:]) & FORBIDDEN_ATTRS:
                    bad(node, f"import of '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level or mod.split(".")[0] not in ALLOWED_IMPORTS or \
                    set(mod.split(".")[1:]) & FORBIDDEN_ATTRS:
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
