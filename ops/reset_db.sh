#!/bin/bash
set -e

# Setup Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo -e "${RED}⚠️  WARNING: This will completely WIPE OUT all UNS platform data! ⚠️${NC}"
echo -e "${RED}This includes all tags, namespace nodes, schema types, and time-series telemetry!${NC}"
echo -n "Are you sure you want to proceed? [y/N]: "
read -r response

if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Aborting database reset."
    exit 1
fi

echo "Connecting to TimescaleDB container to truncate tables..."

docker exec -i uns-timescaledb psql -U uns_admin -d uns_timeseries << 'EOF'
-- Force terminate all active connections to the database except our own
-- This prevents the TRUNCATE command from hanging/blocking
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'uns_timeseries'
  AND pid <> pg_backend_pid();

-- Disable triggers temporarily to ensure fast cascade truncation
SET session_replication_role = 'replica';

-- Truncate relational tables
TRUNCATE TABLE tags RESTART IDENTITY CASCADE;
TRUNCATE TABLE namespace_nodes RESTART IDENTITY CASCADE;
TRUNCATE TABLE uns_payload_schemas RESTART IDENTITY CASCADE;
TRUNCATE TABLE production_run RESTART IDENTITY CASCADE;
TRUNCATE TABLE tag_source_mapping RESTART IDENTITY CASCADE;
TRUNCATE TABLE tag_change_log RESTART IDENTITY CASCADE;
TRUNCATE TABLE master_data_codes RESTART IDENTITY CASCADE;

-- Truncate hyper tables
TRUNCATE TABLE ts_telemetry RESTART IDENTITY CASCADE;
TRUNCATE TABLE ts_alarms RESTART IDENTITY CASCADE;
TRUNCATE TABLE ts_events RESTART IDENTITY CASCADE;
TRUNCATE TABLE ts_status RESTART IDENTITY CASCADE;
TRUNCATE TABLE ts_measurements RESTART IDENTITY CASCADE;
TRUNCATE TABLE ts_metrics RESTART IDENTITY CASCADE;
TRUNCATE TABLE ts_raw_payloads RESTART IDENTITY CASCADE;

-- Re-enable triggers
SET session_replication_role = 'origin';
EOF

echo -e "${GREEN}✅ Database has been completely reset to a clean state!${NC}"

# Optional: Restart services if they were running
echo "Restarting data-engine and backend services to clear stale caches..."
bash "$SCRIPT_DIR/stop_data_engine.sh" > /dev/null 2>&1 || true
bash "$SCRIPT_DIR/start_data_engine.sh" > /dev/null 2>&1 || true
bash "$SCRIPT_DIR/stop_backend.sh" > /dev/null 2>&1 || true
bash "$SCRIPT_DIR/start_backend.sh" > /dev/null 2>&1 || true

echo -e "${GREEN}✅ All services restarted successfully!${NC}"
