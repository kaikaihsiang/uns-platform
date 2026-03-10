#!/bin/bash

# Setup Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo "Stopping Smart Factory Simulator..."

# Try to find processes matching the pattern
PIDS=$(pgrep -f "smart_factory_sim.py" || true)

if [ -n "$PIDS" ]; then
    for pid in $PIDS; do
        if [ "$pid" != "$$" ]; then
            echo -e "  Found simulator process (PID: $pid), killing it safely (Ctrl+C equivalent)..."
            kill -SIGINT "$pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                 echo "  Force killing..."
                 kill -9 "$pid" 2>/dev/null || true
            fi
        fi
    done
    
    # Remove pid file if it exists
    rm -f "$PROJECT_ROOT/logs/simulator.pid"
    
    echo -e "${GREEN}✅ Simulator has been stopped successfully.${NC}"
else
    echo -e "${YELLOW}No active Smart Factory Simulator processes found.${NC}"
    # Clean up stale pid file
    rm -f "$PROJECT_ROOT/logs/simulator.pid"
fi
