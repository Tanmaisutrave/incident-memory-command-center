#!/usr/bin/env bash
# run.sh — bash equivalent of run.ps1
# Usage: bash scripts/run.sh [--rebuild]
set -euo pipefail
cd "$(dirname "$0")/.."

REBUILD=0
for arg in "$@"; do
  [[ "$arg" == "--rebuild" ]] && REBUILD=1
done

PYTHON=".venv/bin/python"
if [[ ! -f "$PYTHON" ]]; then
  echo "ERROR: .venv not found. Run: python -m venv .venv && pip install -r backend/requirements.txt"
  exit 1
fi

if [[ "$REBUILD" == "1" || ! -f "frontend/dist/index.html" ]]; then
  echo "Building frontend…"
  (cd frontend && node build.mjs)
fi

echo "Open http://127.0.0.1:8000  Press Ctrl+C to stop."
"$PYTHON" -m uvicorn app.main:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port 8000
