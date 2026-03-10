#!/bin/bash
# ==============================================================================
# UNS Platform Demo Seeding Manager
# ==============================================================================
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

cd "$PROJECT_ROOT"

# --- Colors ---
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== UNS Platform Demo Seeding Manager ===${NC}"

# --- 1. Detect Environment ---
function detect_python() {
    if [ -d "$PROJECT_ROOT/backend/.venv" ]; then
        echo "$PROJECT_ROOT/backend/.venv/bin/python"
    elif [ -d "$PROJECT_ROOT/demo/.venv" ]; then
        echo "$PROJECT_ROOT/demo/.venv/bin/python"
    else
        echo "python3"
    fi
}

PYTHON_CMD=$(detect_python)
echo -e "Using Python: ${YELLOW}$PYTHON_CMD${NC}"

# --- 2. Cleanup Function ---
function cleanup() {
    echo -e "\n${YELLOW}Stopping background demo streams...${NC}"
    if [ -f "$LOG_DIR/demo_stream.pid" ]; then
        PID=$(cat "$LOG_DIR/demo_stream.pid")
        kill "$PID" 2>/dev/null || true
        rm "$LOG_DIR/demo_stream.pid"
    fi
}
trap cleanup EXIT

# --- 3. Stage 1: Master Data ---
echo -e "\n[1/3] ${BLUE}Seeding Master Data (SQL)...${NC}"
bash ops/seed_namespace.sh

# --- 4. Stage 2: Hierarchy & Schemas ---
echo -e "\n[2/3] ${BLUE}Initializing ISA-95 Hierarchy & Schemas (API)...${NC}"
# 我們可以使用 Python 處理複雜的 JSON，但封裝在 Bash 流程中
if ! $PYTHON_CMD demo/seed_data.py; then
    echo -e "${RED}Error: Stage 2 Seeding failed.${NC}"
    exit 1
fi

# --- 5. Stage 3: Live Data Streams ---
echo -e "\n[3/3] ${BLUE}Launching Live Data Streams (MQTT)...${NC}"
$PYTHON_CMD demo/publish_data.py > "$LOG_DIR/demo_stream.log" 2>&1 &
echo $! > "$LOG_DIR/demo_stream.pid"

echo -e "\n${GREEN}✅ Demo Seeding Successfully Completed!${NC}"
echo -e "Live data log: ${YELLOW}tail -f logs/demo_stream.log${NC}"
echo ""
echo -e "Next steps:"
echo -e "1. Open Frontend Tag Overview to see the tree."
echo -e "2. Run 'python3 demo/smart_factory_sim.py --scenario lifecycle' for full lifecycle."
echo -e "3. Press CTRL+C to stop simulation and exit."

# Keep alive to see logs or wait for user interruption
while true; do sleep 10; done
