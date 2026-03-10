-- ═══════════════════════════════════════════════════════════════
-- UNS Measurement Data + Equipment State Model — Schema
-- ═══════════════════════════════════════════════════════════════
--
-- 此腳本建立：
--   1. ts_measurements 表（品質量測資料，SPC 用）
--   2. equipment_state_def 表（設備狀態枚舉，E10 簡化版）
--   3. 修改 ts_status 加上 state_code
--   4. equipment_oee View（OEE Availability 自動計算）
--
-- 執行順序：在 timeseries_schema.sql 之後執行
--   psql -U uns_admin -d uns_timeseries -f measurement_and_state_schema.sql
-- ═══════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════
-- 1. Measurement Data（品質量測）
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ts_measurements (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),

    -- 量測值
    value           DOUBLE PRECISION NOT NULL,

    -- 規格限（SPC 管制圖用）
    spec_upper      DOUBLE PRECISION,           -- USL
    spec_lower      DOUBLE PRECISION,           -- LSL
    target_value    DOUBLE PRECISION,           -- 目標值

    -- 判定
    result          TEXT DEFAULT 'pass',         -- pass / fail / warning / oos

    -- 生產上下文
    run_id          INTEGER,
    lot_id          TEXT,
    step_id         TEXT,

    -- 取樣
    sample_id       TEXT,
    sample_position TEXT,                        -- head / middle / tail / left / right
    inspector       TEXT,                        -- Pharma 合規

    -- 擴展
    context         JSONB
);

SELECT create_hypertable('ts_measurements', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => true
);

CREATE INDEX IF NOT EXISTS idx_meas_tag_time
    ON ts_measurements(tag_id, time);
CREATE INDEX IF NOT EXISTS idx_meas_lot
    ON ts_measurements(lot_id, time) WHERE lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_run
    ON ts_measurements(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_result
    ON ts_measurements(result, time) WHERE result != 'pass';


-- ═══════════════════════════════════════════════════════════════
-- 2. System Master Data Codes (Generic Dictionary)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS uns_payload_schemas (
    schema_id          SERIAL PRIMARY KEY,
    schema_name        TEXT NOT NULL UNIQUE,
    schema_category    TEXT NOT NULL DEFAULT 'telemetry',
    decoder            TEXT DEFAULT 'json',
    timestamp_field    TEXT,                    -- JSONPath to timestamp in payload
    store_raw          BOOLEAN DEFAULT true,
    raw_retention_days INTEGER DEFAULT 30,
    on_schema_mismatch TEXT DEFAULT 'log_and_store',
    on_new_field       TEXT DEFAULT 'suggest',
    fields             JSONB NOT NULL,          -- Array of field definitions
    version            INTEGER DEFAULT 1,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO master_data_codes (code_category, code_value, label, metadata, description) VALUES
    ('equipment_state', 'PRD', 'Productive', '{"oee_bucket": "availability", "color": "#4CAF50"}', '正常加工中'),
    ('equipment_state', 'SBY', 'Standby', '{"oee_bucket": "availability", "color": "#FFC107"}', '待機中/換線'),
    ('equipment_state', 'ENG', 'Engineering', '{"oee_bucket": "excluded", "color": "#7E57C2"}', '工程測試/校正'),
    ('equipment_state', 'UDT', 'Unscheduled Downtime', '{"oee_bucket": "availability", "color": "#F44336"}', '非計畫停機（故障/警報）'),
    ('equipment_state', 'SDT', 'Scheduled Downtime', '{"oee_bucket": "availability", "color": "#2196F3"}', '計畫保養'),
    ('equipment_state', 'NSC', 'Non-Scheduled', '{"oee_bucket": "excluded", "color": "#9E9E9E"}', '非排班時間')
ON CONFLICT (code_category, code_value) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
-- 3. 修改 ts_status：加上 state 索引
-- ═══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_status_state
    ON ts_status(tag_id, state, time);


-- ═══════════════════════════════════════════════════════════════
-- 4. OEE Availability View
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW equipment_oee AS
WITH state_durations AS (
    SELECT
        s.tag_id,
        DATE_TRUNC('day', s.time) AS day,
        e.label AS state_category,
        e.metadata->>'oee_bucket' AS oee_bucket,
        EXTRACT(EPOCH FROM (
            LEAD(s.time) OVER (PARTITION BY s.tag_id ORDER BY s.time) - s.time
        )) AS duration_seconds
    FROM ts_status s
    JOIN master_data_codes e ON s.state = e.code_value AND e.code_category = 'equipment_state'
    WHERE s.state IS NOT NULL
),
daily_summary AS (
    SELECT
        tag_id, day,
        SUM(duration_seconds) FILTER (WHERE oee_bucket = 'availability') AS scheduled_seconds,
        SUM(duration_seconds) FILTER (WHERE state_category = 'productive') AS productive_seconds,
        SUM(duration_seconds) FILTER (WHERE state_category = 'down') AS down_seconds,
        SUM(duration_seconds) FILTER (WHERE state_category = 'standby') AS standby_seconds
    FROM state_durations
    WHERE (oee_bucket IS NULL OR oee_bucket != 'excluded')
    GROUP BY tag_id, day
)
SELECT
    t.asset_path,
    t.display_name,
    ds.day,
    ds.scheduled_seconds,
    ds.productive_seconds,
    ds.down_seconds,
    ds.standby_seconds,
    ROUND(100.0 * ds.productive_seconds / NULLIF(ds.scheduled_seconds, 0), 1) AS availability_pct
FROM daily_summary ds
JOIN tags t ON ds.tag_id = t.tag_id
ORDER BY t.asset_path, ds.day;


-- ═══════════════════════════════════════════════════════════════
-- 5. SPC Summary View（X-bar 快速查詢）
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW spc_summary AS
SELECT
    t.data_point AS parameter,
    r.product_id,
    r.lot_id,
    r.start_time::DATE AS production_date,
    COUNT(*) AS sample_count,
    AVG(m.value) AS x_bar,
    STDDEV(m.value) AS std_dev,
    MAX(m.value) - MIN(m.value) AS range_r,
    MIN(m.value) AS min_value,
    MAX(m.value) AS max_value,
    MIN(m.spec_lower) AS lsl,
    MAX(m.spec_upper) AS usl,
    MIN(m.target_value) AS target,
    COUNT(*) FILTER (WHERE m.result = 'oos') AS oos_count
FROM ts_measurements m
JOIN tags t ON m.tag_id = t.tag_id
LEFT JOIN production_run r ON m.run_id = r.run_id
GROUP BY t.data_point, r.product_id, r.lot_id, r.start_time::DATE
ORDER BY r.start_time::DATE;


-- ═══════════════════════════════════════════════════════════════
-- 6. 驗證
-- ═══════════════════════════════════════════════════════════════

DO $$
BEGIN
    RAISE NOTICE '✅ ts_measurements 表已建立';
    RAISE NOTICE '✅ master_data_codes 表已建立';
    RAISE NOTICE '✅ ts_status 已加上 state 索引';
    RAISE NOTICE '✅ equipment_oee view 已建立';
    RAISE NOTICE '✅ spc_summary view 已建立';
END $$;
