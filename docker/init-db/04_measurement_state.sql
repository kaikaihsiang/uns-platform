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
