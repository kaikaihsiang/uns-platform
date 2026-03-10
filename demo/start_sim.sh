#!/bin/bash
set -e

# Setup Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo -e "${BLUE}=== Starting Smart Factory Simulator ===${NC}"

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
    echo "Could not find a valid .venv with paho-mqtt installed."
    exit 1
fi

echo "Using python from: $VENV_PATH"

# Ensure logs directory
mkdir -p "$PROJECT_ROOT/logs"

# Check if already running
if [ -f "$PROJECT_ROOT/logs/simulator.pid" ] && kill -0 $(cat "$PROJECT_ROOT/logs/simulator.pid") 2>/dev/null; then
    echo "Simulator is already running with PID $(cat $PROJECT_ROOT/logs/simulator.pid)"
    echo "Tail the log: tail -f logs/simulator.log"
    exit 0
fi

if [ "$1" == "--foreground" ] || [ "$1" == "-f" ]; then
    echo "Running in foreground mode..."
    $VENV_PATH "$SCRIPT_DIR/smart_factory_sim.py"
else
    echo "Running in background mode... (Log: logs/simulator.log)"
    nohup $VENV_PATH "$SCRIPT_DIR/smart_factory_sim.py" > "$PROJECT_ROOT/logs/simulator.log" 2>&1 &
    SIM_PID=$!
    echo $SIM_PID > "$PROJECT_ROOT/logs/simulator.pid"
    echo -e "${GREEN}✅ Simulator started with PID $SIM_PID${NC}"
    echo -e "To tail logs, run: tail -f logs/simulator.log"
    echo -e "To stop, run: demo/stop_sim.sh"
fi
