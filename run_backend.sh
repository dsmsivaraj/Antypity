#!/bin/bash

set -euo pipefail

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-9500}"

# ── Kill any process already holding the port ────────────────────────────────
echo "Checking port $API_PORT..."
PIDS=$(lsof -ti:"$API_PORT" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "Killing existing process(es) on port $API_PORT: $PIDS"
  echo "$PIDS" | xargs kill -9
  sleep 1
fi

# ── Set PYTHONPATH BEFORE activating venv ────────────────────────────────────
export PYTHONPATH="$PROJECT_ROOT"

# ── Activate venv ────────────────────────────────────────────────────────────
source backend/venv/bin/activate

echo "Backend starting on $API_HOST:$API_PORT"
echo "PYTHONPATH: $PYTHONPATH"

# ── Start server ─────────────────────────────────────────────────────────────
# Run without --reload to avoid subprocess PYTHONPATH issues
exec uvicorn backend.main:app --host "$API_HOST" --port "$API_PORT"
