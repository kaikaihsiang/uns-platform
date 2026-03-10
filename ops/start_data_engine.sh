#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# Check if .venv exists
VENV_PATH=""
if [ -d "$PROJECT_ROOT/backend/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/backend/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/demo/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/demo/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/data-engine/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/data-engine/.venv/bin/python"
fi

if [ -z "$VENV_PATH" ]; then
    echo "Could not find a valid .venv."
    exit 1
fi

cd "$PROJECT_ROOT/data-engine"
echo "Starting Data Engine (python)..."
nohup "$VENV_PATH" main.py > "$PROJECT_ROOT/logs/data_engine.log" 2>&1 &
DATA_ENGINE_PID=$!
echo $DATA_ENGINE_PID > "$PROJECT_ROOT/logs/data_engine.pid"

echo "Data Engine started with PID $DATA_ENGINE_PID"
