#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

cd "$PROJECT_ROOT/frontend"
echo "Starting Frontend (Vite)..."
nohup npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PROJECT_ROOT/logs/frontend.pid"

echo "Frontend started with PID $FRONTEND_PID"
