#!/bin/bash
set -e

# Setup Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

# 1. Detect VENV
VENV_PATH=""
if [ -d "$PROJECT_ROOT/backend/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/backend/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/demo/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/demo/.venv/bin/python"
fi

if [ -z "$VENV_PATH" ]; then
    echo -e "${YELLOW}Warning: Could not find .venv. Trying system python3...${NC}"
    VENV_PATH="python3"
fi

show_help() {
    echo "Usage: ./demo/run_test.sh [scenario]"
    echo ""
    echo "Scenarios:"
    echo "  seed         - Run namespace & master data seeding"
    echo "  telemetry    - Send 10 telemetry messages"
    echo "  status       - Send equipment status update"
    echo "  alarm        - Send critical alarm"
    echo "  event        - Send production event"
    echo "  measurement  - Send AOI measurement"
    echo "  metrics      - Send OEE metrics"
    echo "  lifecycle    - Run full 3-board production cycle"
    echo "  all          - Run everything (seed + lifecycle)"
}

if [ -z "$1" ]; then
    show_help
    exit 1
fi

case "$1" in
    seed)
        echo -e "${BLUE}>>> Seeding Namespace & Master Data...${NC}"
        bash "$PROJECT_ROOT/ops/seed_namespace.sh"
        ;;
    telemetry|status|alarm|event|measurement|metrics)
        echo -e "${BLUE}>>> Running Scenario: $1${NC}"
        $VENV_PATH "$SCRIPT_DIR/smart_factory_sim.py" --scenario "$1" --count 10
        ;;
    lifecycle)
        echo -e "${BLUE}>>> Running Production Lifecycle...${NC}"
        $VENV_PATH "$SCRIPT_DIR/smart_factory_sim.py" --scenario "lifecycle" --interval 1.5
        ;;
    all)
        echo -e "${BLUE}>>> Running Full Test Suite...${NC}"
        bash "$PROJECT_ROOT/ops/seed_namespace.sh"
        $VENV_PATH "$SCRIPT_DIR/smart_factory_sim.py" --scenario "lifecycle" --interval 1.0
        ;;
    *)
        show_help
        exit 
        ;;
esac

echo -e "${GREEN}✅ Finished: $1${NC}"
