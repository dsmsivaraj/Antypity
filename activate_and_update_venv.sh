#!/bin/bash

set -euo pipefail

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Activate venv
source backend/venv/bin/activate

# Set PYTHONPATH to project root
export PYTHONPATH="$PROJECT_ROOT"

echo "Virtual environment activated"
echo "PYTHONPATH set to: $PYTHONPATH"

# Update pip and install requirements
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "Virtual environment updated with latest dependencies"
