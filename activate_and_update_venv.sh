#!/bin/bash

set -euo pipefail

export PYTHONPATH="$(pwd)"
source backend/venv/bin/activate

echo "Virtual environment activated and PYTHONPATH set to $PYTHONPATH"

pip install --upgrade pip
pip install -r backend/requirements.txt

echo "Virtual environment updated"
