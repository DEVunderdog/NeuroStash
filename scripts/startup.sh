#!/bin/bash

set -euo pipefail

VENV_DIR="venv"

# Create venv if not exists
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi

# Activate venv
source "$VENV_DIR/bin/activate"

echo "=== Starting initial operations ==="
python -m app.initial_ops
echo "=== Initial setup completed ==="

echo "=== Starting pre-start checks ==="
python -m app.pre_start
echo "=== Pre-start checks completed ==="

echo "=== Launching the main application ==="
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
