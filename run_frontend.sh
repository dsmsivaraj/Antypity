#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT/frontend"

FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# ── Kill any process already holding the port ────────────────────────────────
echo "Checking port $FRONTEND_PORT..."
PIDS=$(lsof -ti:"$FRONTEND_PORT" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "Killing existing process(es) on port $FRONTEND_PORT: $PIDS"
  echo "$PIDS" | xargs kill -9
  sleep 1
fi

# ── Install dependencies if node_modules is missing ──────────────────────────
if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "Frontend starting on http://localhost:$FRONTEND_PORT"

# ── Start Vite dev server ─────────────────────────────────────────────────────
exec npm run dev -- --port "$FRONTEND_PORT"
