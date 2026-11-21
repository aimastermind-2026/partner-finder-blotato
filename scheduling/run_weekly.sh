#!/bin/zsh
# Weekly partner-finder run, started by launchd (see com.blotato.partner-finder.plist).
# Runs the find-partners skill headless. Only local file and Python tools are
# allowed, and claude.ai connectors (Gmail etc.) are switched off, so the run
# cannot send or contact anything.
set -u
PROJECT="/Users/crypto/partner-finder"
LOG="$PROJECT/output/weekly.log"
mkdir -p "$PROJECT/output"
cd "$PROJECT" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

{
  echo "=== $(date '+%Y-%m-%d %H:%M') weekly partner-finder run ==="
  if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements.txt
  fi
  claude -p "/find-partners" \
    --settings '{"disableClaudeAiConnectors": true}' \
    --strict-mcp-config \
    --allowedTools "Read" "Edit(output/**)" \
      "Bash(.venv/bin/python *)" "Bash($PROJECT/.venv/bin/python *)"
  rc=$?
  echo "=== finished $(date '+%H:%M'), exit $rc ==="
} >> "$LOG" 2>&1
