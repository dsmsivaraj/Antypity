#!/bin/bash

set -euo pipefail

source activate_and_update_venv.sh

export PYTHONPATH="$(pwd)"
export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-8000}"

uvicorn backend.main:app --reload --host "$API_HOST" --port "$API_PORT"
