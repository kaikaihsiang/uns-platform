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
-- 目的：優化 GetSnapshot 效能，避免跨超表查詢最新值
-- 由 Data Engine DBWriter 在寫入超表時同步執行 UPSERT

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
    quality     TEXT DEFAULT 'good',
    run_id      INTEGER,
    lot_id      TEXT
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
    run_id          INTEGER,
    lot_id          TEXT,
    details         JSONB
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
    run_id          INTEGER,
    lot_id          TEXT,
    details         JSONB
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
    run_id          INTEGER,
    lot_id          TEXT,
    details         JSONB
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
    run_id        INTEGER
);

SELECT create_hypertable('ts_raw_payloads', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_raw_topic ON ts_raw_payloads(mqtt_topic, time DESC);

COMMENT ON COLUMN ts_raw_payloads.payload_size IS '封包位元組大小 (Byte)';
COMMENT ON COLUMN ts_raw_payloads.schema_id IS '應用之解析 Schema 識別';
