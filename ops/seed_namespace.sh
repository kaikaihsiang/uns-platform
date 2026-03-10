#!/bin/bash
set -e

# Setup Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

echo -e "${BLUE}=== Starting Namespace & Schema Seeding ===${NC}"

echo "Seeding Master Data Codes..."
docker exec -i uns-timescaledb psql -U uns_admin -d uns_timeseries << 'EOF'
-- Equipment State (SEMI E10)
INSERT INTO master_data_codes (code_category, code_value, sub_code_value, label, metadata, description) VALUES
    ('equipment_state', 'PRD', 'RUN', 'Productive - Running', '{"oee_bucket": "availability", "color": "#4CAF50"}', '正常生產中'),
    ('equipment_state', 'PRD', 'SET', 'Productive - Setup', '{"oee_bucket": "availability", "color": "#8BC34A"}', '換線/調機中'),
    ('equipment_state', 'SBY', 'IDL', 'Standby - Idle', '{"oee_bucket": "availability", "color": "#FFC107"}', '閒置（無工單）'),
    ('equipment_state', 'UDT', 'ALM', 'Unscheduled Down - Alarm', '{"oee_bucket": "availability", "color": "#F44336"}', '異常停機'),
    ('equipment_state', 'SDT', 'MNT', 'Scheduled Down - Maint', '{"oee_bucket": "availability", "color": "#2196F3"}', '計畫性保養'),
    ('equipment_state', 'NSC', '', 'Non-Scheduled', '{"oee_bucket": "excluded", "color": "#9E9E9E"}', '非排班時間')
ON CONFLICT (code_category, code_value, sub_code_value) DO NOTHING;

-- Production Events (ISA-88 / IPC-CFX)
INSERT INTO master_data_codes (code_category, code_value, sub_code_value, label, metadata, description) VALUES
    ('production_lifecycle_code', 'LOT_DISPATCHED', '', 'Lot Dispatched', NULL, '批次生產下發'),
    ('production_lifecycle_code', 'RECIPE_DOWNLOAD', '', 'Recipe Download', NULL, '配方下載完成'),
    ('production_lifecycle_code', 'MATERIAL_LOAD', '', 'Material Loaded', NULL, '物料上機'),
    ('production_lifecycle_code', 'LOT_START', '', 'Lot Started', '{"lifecycle_trigger": "start"}', '批次開始'),
    ('production_lifecycle_code', 'UNIT_IN', '', 'Unit In', NULL, '板件進站'),
    ('production_lifecycle_code', 'UNIT_OUT', '', 'Unit Out', NULL, '板件出站'),
    ('production_lifecycle_code', 'LOT_END', '', 'Lot Ended', '{"lifecycle_trigger": "end"}', '批次結束'),
    ('production_lifecycle_code', 'MATERIAL_UNLOAD', '', 'Material Unloaded', NULL, '物料退機')
ON CONFLICT (code_category, code_value, sub_code_value) DO UPDATE SET metadata = EXCLUDED.metadata;

-- Alarm Codes (ISA-18.2)
INSERT INTO master_data_codes (code_category, code_value, sub_code_value, label, metadata, description) VALUES
    ('alarm_code', 'E-VAC-001', '', 'Vacuum Pump Failed', '{"severity": "critical"}', '真空幫浦失效'),
    ('alarm_code', 'E-VIB-022', '', 'Spindle OverVib', '{"severity": "warning"}', '主軸振動超標'),
    ('alarm_code', 'W-TMP-005', '', 'Temp High Warning', '{"severity": "info"}', '溫度預警'),
    ('alarm_code', 'E-COM-999', '', 'Comm Lost', '{"severity": "emergency"}', '通訊完全中斷')
ON CONFLICT (code_category, code_value, sub_code_value) DO NOTHING;

-- Metric Definitions (OEE)
INSERT INTO master_data_codes (code_category, code_value, sub_code_value, label, metadata, description) VALUES
    ('metric_definition', 'OEE', '', 'Overall Equipment Effectiveness', '{"unit": "%"}', '設備綜合效率'),
    ('metric_definition', 'AVAIL', '', 'Availability', '{"unit": "%"}', '稼動率'),
    ('metric_definition', 'PERF', '', 'Performance', '{"unit": "%"}', '性能表現'),
    ('metric_definition', 'QUAL', '', 'Quality', '{"unit": "%"}', '品質良率')
ON CONFLICT (code_category, code_value, sub_code_value) DO NOTHING;
EOF

# Check if .venv exists in demo directory where previously scripts were, or backend
VENV_PATH=""
if [ -d "$PROJECT_ROOT/backend/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/backend/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/demo/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/demo/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/data-engine/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/data-engine/.venv/bin/python"
fi

if [ -z "$VENV_PATH" ]; then
    echo "Could not find a valid .venv with requests installed. Please ensure backend or demo venv is setup."
    exit 1
fi

echo "Using python from: $VENV_PATH"

# Run the seeding script
$VENV_PATH "$SCRIPT_DIR/scripts/seed_namespace.py"

echo -e "${GREEN}✅ Namespace and Master Data seeded successfully!${NC}"
