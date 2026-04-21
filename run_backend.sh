#!/bin/bash

set -euo pipefail

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Set PYTHONPATH BEFORE activating venv so it's inherited by subprocess
export PYTHONPATH="$PROJECT_ROOT"

# Activate venv
source backend/venv/bin/activate

export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-9500}"

echo "Backend running on $API_HOST:$API_PORT"
echo "PYTHONPATH: $PYTHONPATH"

# Run without reload to avoid subprocess PYTHONPATH issues
uvicorn backend.main:app --host "$API_HOST" --port "$API_PORT"
