#!/usr/bin/env bash
# Run N autoresearch sessions. Each one is a fresh headless Claude Code call that reads
# research/program.md, tries up to 3 strategies, and updates research/notes.md.
#
#   scripts/loop.sh 20                     # 20 sessions
#   LODESTAR_MODEL=claude-opus-5-5 scripts/loop.sh 5
set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-10}"
CLAUDE="${CLAUDE_BIN:-claude}"
MODEL="${LODESTAR_MODEL:-}"

if [ ! -f data/research/bars.parquet ]; then
  echo "No research data. Run: .venv/bin/python -m lodestar fetch" >&2
  exit 1
fi
mkdir -p logs

for i in $(seq 1 "$N"); do
  stamp=$(date +%Y%m%d-%H%M%S)
  before=$(wc -l < research/results.jsonl 2>/dev/null || echo 0)
  echo "== session $i/$N  $stamp"

  # --strict-mcp-config: no MCP servers at all (in particular, no brokerage connectors).
  # --setting-sources project + --settings: ignore user hooks and plugins; use the agent policy.
  # --permission-mode dontAsk: anything not allowed in agent-settings.json is denied.
  "$CLAUDE" -p "$(cat research/program.md)" \
    --settings scripts/agent-settings.json \
    --setting-sources project \
    --strict-mcp-config \
    --tools "Read,Glob,Grep,Edit,Write,Bash" \
    --permission-mode dontAsk \
    ${MODEL:+--model "$MODEL"} \
    < /dev/null > "logs/session-$stamp.log" 2>&1 \
    || echo "   session exited non-zero (see logs/session-$stamp.log)"

  # Belt and braces: stop if anything outside the agent's workspace changed.
  if ! git diff --quiet -- lodestar tests scripts pyproject.toml research/program.md; then
    echo "!! files outside the research workspace changed; stopping. Inspect with git diff." >&2
    exit 3
  fi

  summary=$(.venv/bin/python scripts/session_summary.py "$before")
  echo "   $summary"
  git add research/
  git commit -q -m "research: $summary" || echo "   nothing to commit"
done
