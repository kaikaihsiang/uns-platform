#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

cd "$PROJECT_ROOT/backend"
echo "Starting Backend (uvicorn)..."
nohup .venv/bin/uvicorn app.main:app --port 8000 --reload > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PROJECT_ROOT/logs/backend.pid"

echo "Backend started with PID $BACKEND_PID"
