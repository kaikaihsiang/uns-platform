#!/bin/bash

# Setup Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo -e "${BLUE}=== Stopping UNS Platform MVP ===${NC}"

# 1. Kill Backend
bash "$SCRIPT_DIR/stop_backend.sh"

# 2. Kill Data Engine
bash "$SCRIPT_DIR/stop_data_engine.sh"

# 3. Kill Frontend
bash "$SCRIPT_DIR/stop_frontend.sh"

# 4. Stop Infrastructure (Docker Compose)
echo -e "\nStopping Infrastructure (DB & MQTT) without deleting data..."
docker-compose stop

echo ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}🛑 All services have been stopped successfully!${NC}"
echo -e "${GREEN}==============================================${NC}"
