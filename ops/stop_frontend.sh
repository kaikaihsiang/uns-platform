#!/bin/bash

# Setup Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Function to kill process safely
kill_process() {
    local process_name=$1
    local pgrep_pattern=$2
    local pid_file=$3
    
    echo -e "Stopping ${process_name}..."
    
    local pids=""
    
    # 1. Try to get PID from file first
    if [ -f "$pid_file" ]; then
        pids=$(cat "$pid_file" 2>/dev/null)
        echo -e "  Found PID from file: $pids"
    fi
    
    # 2. Fallback to pgrep if no PID found from file
    if [ -z "$pids" ]; then
        pids=$(pgrep -i -f "$pgrep_pattern" || true)
    fi
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            if [ "$pid" != "$$" ]; then
                echo -e "  Sending SIGTERM to ${process_name} (PID: $pid)..."
                kill -15 "$pid" 2>/dev/null || true
            fi
        done
        sleep 2
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "  Force killing ${process_name} process (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        # Clean up the specific pid file
        rm -f "$pid_file"
    else
        echo -e "  ${YELLOW}No active ${process_name} processes found.${NC}"
    fi
}

kill_process "Frontend (npm/Vite)" "vite" "$PROJECT_ROOT/logs/frontend.pid"
