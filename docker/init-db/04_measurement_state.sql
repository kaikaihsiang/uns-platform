-- =============================================================================
-- 04: Measurement + Equipment State
-- =============================================================================
-- 來源：schemas/measurement_and_state_schema.sql

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
    context         JSONB
);

SELECT create_hypertable('ts_measurements', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => true
);

CREATE INDEX IF NOT EXISTS idx_meas_tag_time ON ts_measurements(tag_id, time);
CREATE INDEX IF NOT EXISTS idx_meas_lot ON ts_measurements(lot_id, time) WHERE lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_run ON ts_measurements(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_result ON ts_measurements(result, time) WHERE result != 'pass';


-- ─── Equipment State Definition（E10 簡化版）─────────────────

CREATE TABLE IF NOT EXISTS equipment_state_def (
    state_code      INTEGER PRIMARY KEY,
    state_name      TEXT NOT NULL UNIQUE,
    state_category  TEXT NOT NULL,
    oee_bucket      TEXT NOT NULL,
    description     TEXT,
    color           TEXT
);

INSERT INTO equipment_state_def VALUES
    (100, 'running',            'productive',     'availability', '正常加工中',         '#4CAF50'),
    (101, 'loading_unloading',  'productive',     'availability', '上下料',             '#8BC34A'),
    (200, 'idle',               'standby',        'availability', '待機中',             '#FFC107'),
    (201, 'setup_changeover',   'standby',        'availability', '換線/換模/換配方',    '#FF9800'),
    (202, 'warmup',             'standby',        'availability', '預熱/穩定中',         '#FFB74D'),
    (203, 'waiting_material',   'standby',        'availability', '等待物料',            '#FFE082'),
    (204, 'waiting_operator',   'standby',        'availability', '等待人員操作',        '#FFD54F'),
    (300, 'planned_maintenance','down',           'availability', '計畫保養',            '#2196F3'),
    (301, 'unplanned_down',     'down',           'availability', '非計畫停機（故障）',   '#F44336'),
    (302, 'repair',             'down',           'availability', '維修中',              '#E53935'),
    (303, 'calibration',        'down',           'availability', '校正中',              '#42A5F5'),
    (400, 'non_scheduled',      'non_scheduled',  'excluded',     '非排班時間',           '#9E9E9E'),
    (401, 'holiday',            'non_scheduled',  'excluded',     '假日停工',             '#BDBDBD'),
    (402, 'engineering',        'non_scheduled',  'excluded',     '工程測試',             '#7E57C2')
ON CONFLICT (state_code) DO NOTHING;


-- ─── ts_status 加上 state_code ───────────────────────────────

ALTER TABLE ts_status ADD COLUMN IF NOT EXISTS state_code INTEGER;
CREATE INDEX IF NOT EXISTS idx_status_code ON ts_status(tag_id, state_code, time);
