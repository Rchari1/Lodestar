"""One-line summary of attempts logged after line N of research/results.jsonl (used in loop commits)."""
import json
import sys
from pathlib import Path

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
path = Path(__file__).resolve().parents[1] / "research" / "results.jsonl"
lines = path.read_text().splitlines()[start:] if path.exists() else []
rows = [json.loads(line) for line in lines if line.strip()]
scored = [r for r in rows if r.get("status") == "scored"]
if not rows:
    print("session made no attempts")
elif not scored:
    print(f"{len(rows)} attempt(s), none scored ({rows[-1]['status']}: {rows[-1]['id']})")
else:
    best = max(scored, key=lambda r: r["mean_fold_sharpe"])
    passed = sum(r["passed"] for r in scored)
    print(f"{best['id']} fold_sharpe={best['mean_fold_sharpe']:.2f} "
          f"({len(rows)} attempt(s), {passed} passed)")
