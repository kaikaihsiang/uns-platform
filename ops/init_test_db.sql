-- =============================================================================
-- Test Database Initialization
-- =============================================================================
-- This script initializes the entire schema for the 'uns_test' database
-- and adds a helper function to reset it.
--
-- How to run from your local machine using Docker:
-- 1. Make sure you have already created the 'uns_test' database using 'create_test_db.sql'.
-- 2. Make sure your TimescaleDB container is running (e.g., 'uns-timescaledb').
-- 3. Execute the command below:
--
-- docker exec -i uns-timescaledb psql -U uns_admin -d uns_test < ops/init_test_db.sql
-- =============================================================================

-- =============================================================================
-- 01: Extensions
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
-- =============================================================================
-- 02: Namespace Nodes + Schema Types
-- =============================================================================
-- 來源：platform_system_spec.md §3.2, §5.6

-- ─── Namespace Nodes ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS namespace_nodes (
    node_id         SERIAL PRIMARY KEY,
    parent_id       INTEGER REFERENCES namespace_nodes(node_id),
    name            TEXT NOT NULL,
    node_type       TEXT NOT NULL,               -- structural / topic
    full_path       TEXT NOT NULL UNIQUE,

    -- Topic Node 專屬
    schema_id       INTEGER,                     -- FK 在 uns_payload_schemas 建立後加
    persist_mode    TEXT DEFAULT 'db',            -- db / retain / passthrough
    retention_days  INTEGER DEFAULT 90,

    -- Metadata
    description     TEXT,
    icon            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ                  -- Soft delete
);

CREATE INDEX IF NOT EXISTS idx_ns_parent ON namespace_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_ns_path ON namespace_nodes(full_path);
CREATE INDEX IF NOT EXISTS idx_ns_type ON namespace_nodes(node_type);

COMMENT ON COLUMN namespace_nodes.node_type IS '節點類型: structural (階層) / topic (資料點)';
COMMENT ON COLUMN namespace_nodes.full_path IS '完整 MQTT Topic 路徑';
COMMENT ON COLUMN namespace_nodes.persist_mode IS '持久化模式: db (存庫) / retain (僅保留最新) / passthrough (僅轉發)';


-- ─── Payload Schemas ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS uns_payload_schemas (
    schema_id          SERIAL PRIMARY KEY,
    schema_name        TEXT NOT NULL UNIQUE,
    schema_category    TEXT NOT NULL DEFAULT 'telemetry',
    decoder            TEXT DEFAULT 'json',
    timestamp_field    TEXT,
    store_raw          BOOLEAN DEFAULT true,
    raw_retention_days INTEGER DEFAULT 30,
    on_schema_mismatch TEXT DEFAULT 'log_and_store',
    on_new_field       TEXT DEFAULT 'suggest',
    fields             JSONB NOT NULL,
    status             TEXT DEFAULT 'confirmed',  -- confirmed / suggested / modified
    is_suggested       BOOLEAN DEFAULT false,
    topic_pattern      TEXT,
    version            INTEGER DEFAULT 1,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW(),
    deleted_at         TIMESTAMPTZ
);

COMMENT ON TABLE uns_payload_schemas IS '定義 MQTT Payload 的解析規則與分類路由';
COMMENT ON COLUMN uns_payload_schemas.schema_category IS '資料分類: telemetry, status, alarm, event, measurement, metrics';
COMMENT ON COLUMN uns_payload_schemas.fields IS 'JSONPath 提取規則陣列';


-- ─── 加上 FK ─────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ns_schema') THEN
        ALTER TABLE namespace_nodes
            ADD CONSTRAINT fk_ns_schema
            FOREIGN KEY (schema_id) REFERENCES uns_payload_schemas(schema_id);
    END IF;
END $$;
-- =============================================================================
-- 03: Time-Series Core Tables
-- =============================================================================
-- 來源：schemas/timeseries_schema.sql + ts_raw_payloads

-- ─── Tags ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tags (
    tag_id        SERIAL PRIMARY KEY,
    display_name  TEXT NOT NULL,
    asset_path    TEXT NOT NULL,
    category      TEXT NOT NULL,
    data_point    TEXT,
    unit          TEXT,
    data_type     TEXT NOT NULL DEFAULT 'float',
    description   TEXT,
    metadata      JSONB DEFAULT '{}',          -- 靜態元數據 (如 vendor, criticality)
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_data_at  TIMESTAMPTZ,
    deleted_at    TIMESTAMPTZ,

    UNIQUE(asset_path, category, data_point)
);

CREATE INDEX IF NOT EXISTS idx_tags_asset_path ON tags(asset_path);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS idx_tags_asset_category ON tags(asset_path, category);
CREATE INDEX IF NOT EXISTS idx_tags_metadata ON tags USING GIN (metadata);

-- ─── Latest Values Snapshot ───────────────────────────────────

CREATE TABLE IF NOT EXISTS latest_values (
    tag_id          INTEGER PRIMARY KEY REFERENCES tags(tag_id),
    time            TIMESTAMPTZ NOT NULL,
    category        TEXT NOT NULL,
    display_value   TEXT,
    data            JSONB NOT NULL,
    quality         TEXT DEFAULT 'good',
    run_id          INTEGER,
    context_data    JSONB
);

CREATE INDEX IF NOT EXISTS idx_lv_run_id ON latest_values(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lv_category ON latest_values(category);


-- ─── Tag Source Mapping ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS tag_source_mapping (
    mapping_id    SERIAL PRIMARY KEY,
    tag_id        INTEGER NOT NULL REFERENCES tags(tag_id),
    mqtt_topic    TEXT NOT NULL UNIQUE,
    active        BOOLEAN NOT NULL DEFAULT true,
    mapped_at     TIMESTAMPTZ DEFAULT NOW(),
    mapped_by     TEXT,
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_mapping_topic ON tag_source_mapping(mqtt_topic) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_mapping_tag ON tag_source_mapping(tag_id);


-- ─── Tag Change Log ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tag_change_log (
    id            SERIAL PRIMARY KEY,
    tag_id        INTEGER NOT NULL REFERENCES tags(tag_id),
    change_type   TEXT NOT NULL,
    old_value     TEXT,
    new_value     TEXT,
    reason        TEXT,
    changed_at    TIMESTAMPTZ DEFAULT NOW(),
    changed_by    TEXT
);


-- ─── Telemetry ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_telemetry (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    value       DOUBLE PRECISION,
    value_text  TEXT,
    value_json  JSONB,
    quality     TEXT DEFAULT 'good'
);

SELECT create_hypertable('ts_telemetry', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_telemetry_tag ON ts_telemetry(tag_id, time DESC);

COMMENT ON COLUMN ts_telemetry.time IS '數據紀錄時間 (ISO8601)';
COMMENT ON COLUMN ts_telemetry.tag_id IS '關連之標籤唯一識別 ID';
COMMENT ON COLUMN ts_telemetry.value IS '數值型觀測值 (float/int)';
COMMENT ON COLUMN ts_telemetry.value_text IS '文字型觀測值 (string/state)';
COMMENT ON COLUMN ts_telemetry.value_json IS '複雜結構 JSON 觀測值';
COMMENT ON COLUMN ts_telemetry.quality IS '數據品質標誌 (good/bad/uncertain)';


-- ─── Status ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_status (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),
    state_code      TEXT NOT NULL,
    sub_state_code  TEXT,
    code_category   TEXT,
    mode            TEXT,
    details         JSONB,
    run_id          INTEGER,
    lot_id          TEXT
);

SELECT create_hypertable('ts_status', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_status_tag ON ts_status(tag_id, time DESC);

COMMENT ON COLUMN ts_status.state_code IS '設備主狀態碼 (對應 master_data_codes.code_value)';
COMMENT ON COLUMN ts_status.sub_state_code IS '設備子狀態碼 (對應 master_data_codes.sub_code_value)';
COMMENT ON COLUMN ts_status.code_category IS '狀態碼分類 (對應 master_data_codes.code_category)';
COMMENT ON COLUMN ts_status.mode IS '運行模式 (Auto/Manual/Semi-Auto)';
COMMENT ON COLUMN ts_status.details IS '額外狀態補充資訊';


-- ─── Alarms ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_alarms (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),
    alarm_id        TEXT NOT NULL,
    alarm_code      TEXT NOT NULL,
    sub_alarm_code  TEXT,
    code_category   TEXT,
    severity        TEXT NOT NULL,
    message         TEXT,
    alarm_status    TEXT NOT NULL,
    value           DOUBLE PRECISION,
    threshold       DOUBLE PRECISION,
    details         JSONB,
    run_id          INTEGER,
    lot_id          TEXT
);

SELECT create_hypertable('ts_alarms', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_alarms_tag ON ts_alarms(tag_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ts_alarms_severity ON ts_alarms(severity, time DESC);

COMMENT ON COLUMN ts_alarms.alarm_id IS '告警執行個體唯一編號';
COMMENT ON COLUMN ts_alarms.alarm_code IS '主告警代碼';
COMMENT ON COLUMN ts_alarms.sub_alarm_code IS '解析用子告警代碼';
COMMENT ON COLUMN ts_alarms.severity IS '嚴重程度 (critical/warning/info)';
COMMENT ON COLUMN ts_alarms.alarm_status IS '當前告警狀態 (active/cleared/acknowledged)';
COMMENT ON COLUMN ts_alarms.value IS '觸發告警當下的觀測值 (Optional)';
COMMENT ON COLUMN ts_alarms.threshold IS '觸發告警之預設閾值 (Optional)';


-- ─── Events ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_events (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),
    event_id        TEXT NOT NULL,
    event_code      TEXT NOT NULL,
    sub_event_code  TEXT,
    code_category   TEXT,
    result          TEXT,
    details         JSONB,
    run_id          INTEGER,
    lot_id          TEXT
);

SELECT create_hypertable('ts_events', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_events_tag ON ts_events(tag_id, time DESC);

COMMENT ON COLUMN ts_events.event_code IS '主事件名稱/代碼';
COMMENT ON COLUMN ts_events.sub_event_code IS '子事件描述或代碼';
COMMENT ON COLUMN ts_events.result IS '事件執行結果 (Success/Failed/Aborted)';


-- ─── Metrics ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_metrics (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),
    metric_category TEXT NOT NULL,
    metric_code     TEXT NOT NULL,
    sub_metric_code TEXT,
    period          TEXT,
    values          JSONB NOT NULL,
    run_id          INTEGER,
    lot_id          TEXT,
    context         JSONB,
    details         JSONB
);

SELECT create_hypertable('ts_metrics', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_metrics_tag ON ts_metrics(tag_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ts_metrics_cat ON ts_metrics(metric_category, time DESC);

COMMENT ON COLUMN ts_metrics.metric_category IS '指標分類代碼 (對應 master_data_codes.code_category)';
COMMENT ON COLUMN ts_metrics.metric_code IS '指標主代碼 (如 OEE, UPH)';
COMMENT ON COLUMN ts_metrics.sub_metric_code IS '指標延伸代碼';
COMMENT ON COLUMN ts_metrics.period IS '計算週期 (Hourly/Shift/Daily)';
COMMENT ON COLUMN ts_metrics.values IS '多維度指標量化值 (JSONB 存儲)';


-- ─── Measurements ──────────────────────────────────────────────
-- 注意：權威定義已移至 04_measurement_state.sql


-- ─── Raw Payloads（Dual Storage）─────────────────────────────

CREATE TABLE IF NOT EXISTS ts_raw_payloads (
    time          TIMESTAMPTZ NOT NULL,
    mqtt_topic    TEXT NOT NULL,
    payload       JSONB NOT NULL,
    payload_size  INTEGER,
    schema_id     INTEGER,
    run_id        INTEGER,
    lot_id        TEXT
);

SELECT create_hypertable('ts_raw_payloads', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_raw_topic ON ts_raw_payloads(mqtt_topic, time DESC);

COMMENT ON COLUMN ts_raw_payloads.payload_size IS '封包位元組大小 (Byte)';
COMMENT ON COLUMN ts_raw_payloads.schema_id IS '應用之解析 Schema 識別';
-- ─── Measurements（SPC 用）────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_measurements (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),
    value           DOUBLE PRECISION NOT NULL,
    spec_upper      DOUBLE PRECISION,
    spec_lower      DOUBLE PRECISION,
    target_value    DOUBLE PRECISION,
    result          TEXT DEFAULT 'pass',
    run_id          INTEGER,
    lot_id          TEXT,
    step_id         TEXT,
    sample_id       TEXT,
    sample_position TEXT,
    inspector       TEXT,
    context         JSONB,
    details         JSONB
);

SELECT create_hypertable('ts_measurements', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => true
);

CREATE INDEX IF NOT EXISTS idx_meas_tag_time ON ts_measurements(tag_id, time);
CREATE INDEX IF NOT EXISTS idx_meas_lot ON ts_measurements(lot_id, time) WHERE lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_run ON ts_measurements(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_result ON ts_measurements(result, time) WHERE result != 'pass';

COMMENT ON COLUMN ts_measurements.value IS '量測觀測值';
COMMENT ON COLUMN ts_measurements.target_value IS '量測目標中心值 (用於 Cpk 計算)';
COMMENT ON COLUMN ts_measurements.spec_upper IS '規格上限 (USL)';
COMMENT ON COLUMN ts_measurements.spec_lower IS '規格下限 (LSL)';
COMMENT ON COLUMN ts_measurements.result IS '判定結果 (pass/fail/warn)';
COMMENT ON COLUMN ts_measurements.sample_id IS '樣本識別碼 (如板號、條碼)';
COMMENT ON COLUMN ts_measurements.inspector IS '執行檢驗之人員或機台 ID';


-- ─── System Master Data Codes (Generic Dictionary) ───────────

CREATE TABLE IF NOT EXISTS master_data_codes (
    code_category   TEXT NOT NULL,
    code_value      TEXT NOT NULL,
    sub_code_value  TEXT NOT NULL DEFAULT '',
    label           TEXT NOT NULL,
    metadata        JSONB,
    description     TEXT,
    PRIMARY KEY (code_category, code_value, sub_code_value)
);

COMMENT ON COLUMN master_data_codes.code_category IS '主數據類別 (如 equipment_state, alarm_code, production_lifecycle_code)';
COMMENT ON COLUMN master_data_codes.code_value IS '主代碼 (如 PRD, UDT)';
COMMENT ON COLUMN master_data_codes.sub_code_value IS '子代碼 (預設為空字串，用於層級化分類)';
COMMENT ON COLUMN master_data_codes.label IS '顯示名稱/標籤';
COMMENT ON COLUMN master_data_codes.metadata IS '額外元數據 (如 UI 顏色、計算權重)';

INSERT INTO master_data_codes (code_category, code_value, sub_code_value, label, metadata, description) VALUES
    ('equipment_state', 'PRD', '', 'Productive', '{"oee_bucket": "availability", "color": "#4CAF50"}', '正常加工中'),
    ('equipment_state', 'SBY', '', 'Standby', '{"oee_bucket": "availability", "color": "#FFC107"}', '待機中/換線'),
    ('equipment_state', 'ENG', '', 'Engineering', '{"oee_bucket": "excluded", "color": "#7E57C2"}', '工程測試/校正'),
    ('equipment_state', 'UDT', '', 'Unscheduled Downtime', '{"oee_bucket": "availability", "color": "#F44336"}', '非計畫停機'),
    ('equipment_state', 'UDT', 'E-VAC-LOSS', 'Vacuum Loss', '{"oee_bucket": "availability"}', '真空吸力不足 (故障細分)'),
    ('equipment_state', 'SDT', '', 'Scheduled Downtime', '{"oee_bucket": "availability", "color": "#2196F3"}', '計畫保養'),
    ('equipment_state', 'NSC', '', 'Non-Scheduled', '{"oee_bucket": "excluded", "color": "#9E9E9E"}', '非排班時間'),
    ('metric_definition', 'OEE', '', 'Overall Equipment Effectiveness', '{"unit": "%"}', '設備綜合效率'),
    ('production_lifecycle_code', 'LOT_START', '', 'Lot Start', '{"lifecycle_trigger": "start"}', '生產批次開始 (Metadata Trigger)'),
    ('production_lifecycle_code', 'LOT_END', '', 'Lot End', '{"lifecycle_trigger": "end"}', '生產批次結束 (Metadata Trigger)')
ON CONFLICT (code_category, code_value, sub_code_value) DO NOTHING;

-- ─── ts_status Index on state ───────────────────────────────

CREATE INDEX IF NOT EXISTS idx_status_state ON ts_status(tag_id, state_code, time);
-- =============================================================================
-- 05: Production Context
-- =============================================================================
-- 來源：schemas/production_context_schema.sql

-- ─── Production Run ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS production_run (
    run_id          SERIAL PRIMARY KEY,
    lot_id          TEXT NOT NULL,
    parent_lot_id   TEXT,
    equipment_path  TEXT NOT NULL,
    chamber_id      TEXT,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,
    step_id         TEXT NOT NULL,
    pass_number     INTEGER DEFAULT 1,
    recipe_id       TEXT,
    recipe_version  TEXT,
    product_id      TEXT,
    status          TEXT DEFAULT 'running',
    result          TEXT,
    qty_in          INTEGER,
    qty_out         INTEGER,
    context         JSONB,
    source          TEXT DEFAULT 'cdc',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_equipment_time ON production_run(equipment_path, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_run_lot ON production_run(lot_id, start_time);
CREATE INDEX IF NOT EXISTS idx_run_product_step ON production_run(product_id, step_id);
CREATE INDEX IF NOT EXISTS idx_run_active ON production_run(equipment_path) WHERE end_time IS NULL;
CREATE INDEX IF NOT EXISTS idx_run_parent ON production_run(parent_lot_id) WHERE parent_lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_run_context ON production_run USING GIN(context);


-- ─── ts_telemetry 加上 production context ────────────────────

ALTER TABLE ts_telemetry ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_telemetry ADD COLUMN IF NOT EXISTS lot_id TEXT;
ALTER TABLE ts_telemetry ADD COLUMN IF NOT EXISTS step_id TEXT;

CREATE INDEX IF NOT EXISTS idx_telemetry_lot ON ts_telemetry(lot_id, time) WHERE lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_telemetry_run ON ts_telemetry(run_id) WHERE run_id IS NOT NULL;


-- ─── 其他 ts_* 表也加上 ──────────────────────────────────────

ALTER TABLE ts_status ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_status ADD COLUMN IF NOT EXISTS lot_id TEXT;

ALTER TABLE ts_alarms ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_alarms ADD COLUMN IF NOT EXISTS lot_id TEXT;

ALTER TABLE ts_events ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_events ADD COLUMN IF NOT EXISTS lot_id TEXT;

ALTER TABLE ts_metrics ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_metrics ADD COLUMN IF NOT EXISTS lot_id TEXT;


-- ─── Views ───────────────────────────────────────────────────

CREATE OR REPLACE VIEW active_runs AS
SELECT run_id, lot_id, equipment_path, chamber_id,
       step_id, pass_number, recipe_id, product_id,
       start_time, context
FROM production_run
WHERE end_time IS NULL AND status = 'running';

CREATE OR REPLACE VIEW lot_history AS
SELECT lot_id, parent_lot_id, step_id, pass_number,
       equipment_path, chamber_id, recipe_id, product_id,
       start_time, end_time, status, result, qty_in, qty_out,
       EXTRACT(EPOCH FROM (COALESCE(end_time, NOW()) - start_time)) AS duration_seconds
FROM production_run
ORDER BY lot_id, start_time;


-- =============================================================================
-- Test Database Reset Function
-- =============================================================================
-- This function provides a single, easy-to-call procedure to completely
-- wipe all data from the test database, resetting it to a clean state.
-- It's designed to be called before each test run.
--
-- How to use in tests (e.g., with psycopg2):
-- with conn.cursor() as cursor:
--     cursor.execute("SELECT truncate_all_tables_test();")
-- =============================================================================

CREATE OR REPLACE FUNCTION truncate_all_tables_test() RETURNS void AS $$
BEGIN
    -- Disable triggers temporarily to ensure fast cascade truncation
    SET session_replication_role = 'replica';

    -- Truncate relational tables
    TRUNCATE TABLE public.tags RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.namespace_nodes RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.uns_payload_schemas RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.production_run RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.tag_source_mapping RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.tag_change_log RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.master_data_codes RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.latest_values RESTART IDENTITY CASCADE;

    -- Truncate hyper tables
    TRUNCATE TABLE public.ts_telemetry RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.ts_alarms RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.ts_events RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.ts_status RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.ts_measurements RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.ts_metrics RESTART IDENTITY CASCADE;
    TRUNCATE TABLE public.ts_raw_payloads RESTART IDENTITY CASCADE;

    -- Re-enable triggers
    SET session_replication_role = 'origin';
END;
$$ LANGUAGE plpgsql;
