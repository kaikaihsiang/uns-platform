#!/bin/bash
set -e

# Setup Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

echo -e "${BLUE}=== Starting UNS Platform MVP ===${NC}"

# Navigate to project root automatically
cd "$PROJECT_ROOT"

# Ensure directories exist
mkdir -p ops logs

# 1. Start Infrastructure
bash "$SCRIPT_DIR/start_infra.sh"

# 2. Start Backend
bash "$SCRIPT_DIR/start_backend.sh"

# 3. Start Data Engine
bash "$SCRIPT_DIR/start_data_engine.sh"

# 4. Start Frontend
bash "$SCRIPT_DIR/start_frontend.sh"

echo ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}🎉 All services have been started successfully!${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e "Frontend App  : ${BLUE}http://localhost:3000${NC}"
echo -e "Backend API   : ${BLUE}http://localhost:8000/docs${NC}"
echo -e "MQTT Broker   : ${BLUE}http://localhost:18083${NC} (admin/public)"
echo -e "=============================================="
echo -e "To stop all services, run: ${BLUE}ops/stop_all.sh${NC}"
echo ""
