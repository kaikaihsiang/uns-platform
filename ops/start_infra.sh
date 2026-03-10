#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

echo "Starting DB and MQTT infrastructure..."
docker-compose up -d

echo "Waiting for 5 seconds to ensure DB is ready..."
sleep 5
echo "Infrastructure is ready!"
