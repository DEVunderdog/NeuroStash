#!/bin/bash

set -euo pipefail

echo "=== Running database migration ==="
alembic upgrade head

echo "=== Starting initial operations ==="
python -m app.initial_ops
echo "=== Initial setup completed ==="

echo "=== Starting pre-start checks ==="
python -m app.pre_start
echo "=== Pre-start checks completed ==="

echo "=== Launching the main application ==="
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
