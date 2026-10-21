"""SHA-256 manifest of every .py file in the lodestar package.

`evaluate` refuses to score if the harness differs from the manifest, so an agent
can't quietly loosen the rules it's scored by. Regenerating it (`lodestar rehash`)
is a human action and shows up in git.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "harness/MANIFEST.sha256"


def compute_manifest(pkg_dir: Path = PACKAGE_DIR) -> dict[str, str]:
    pkg_dir = Path(pkg_dir)
    out = {}
    for f in sorted(pkg_dir.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        out[f.relative_to(pkg_dir).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def write_manifest(pkg_dir: Path = PACKAGE_DIR) -> Path:
    path = Path(pkg_dir) / MANIFEST_NAME
    lines = [f"{digest}  {rel}" for rel, digest in compute_manifest(pkg_dir).items()]
    path.write_text("\n".join(lines) + "\n")
    return path


def verify_manifest(pkg_dir: Path = PACKAGE_DIR) -> list[str]:
    path = Path(pkg_dir) / MANIFEST_NAME
    if not path.exists():
        return [f"manifest missing: {MANIFEST_NAME}"]
    expected = {}
    for line in path.read_text().splitlines():
        if line.strip():
            digest, rel = line.split(maxsplit=1)
            expected[rel] = digest
    actual = compute_manifest(pkg_dir)
    problems = [f"modified: {r}" for r in expected if r in actual and actual[r] != expected[r]]
    problems += [f"missing: {r}" for r in expected if r not in actual]
    problems += [f"unexpected: {r}" for r in actual if r not in expected]
    return problems
