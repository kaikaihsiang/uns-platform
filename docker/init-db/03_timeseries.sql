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
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_data_at  TIMESTAMPTZ,

    UNIQUE(asset_path, category, data_point)
);

CREATE INDEX IF NOT EXISTS idx_tags_asset_path ON tags(asset_path);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS idx_tags_asset_category ON tags(asset_path, category);


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


-- ─── Status ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_status (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    state       TEXT NOT NULL,
    sub_state   TEXT,
    mode        TEXT
);

SELECT create_hypertable('ts_status', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_status_tag ON ts_status(tag_id, time DESC);


-- ─── Alarms ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_alarms (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    alarm_id    TEXT NOT NULL,
    code        TEXT NOT NULL,
    severity    TEXT NOT NULL,
    message     TEXT,
    state       TEXT NOT NULL,
    value       DOUBLE PRECISION,
    threshold   DOUBLE PRECISION
);

SELECT create_hypertable('ts_alarms', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_alarms_tag ON ts_alarms(tag_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ts_alarms_severity ON ts_alarms(severity, time DESC);


-- ─── Events ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_events (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    event_id    TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    result      TEXT,
    details     JSONB
);

SELECT create_hypertable('ts_events', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_events_tag ON ts_events(tag_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ts_events_type ON ts_events(event_type, time DESC);


-- ─── Metrics ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ts_metrics (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    metric_type TEXT NOT NULL,
    period      TEXT,
    values      JSONB NOT NULL,
    context     JSONB
);

SELECT create_hypertable('ts_metrics', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_metrics_tag ON ts_metrics(tag_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ts_metrics_type ON ts_metrics(metric_type, time DESC);


-- ─── Raw Payloads（Dual Storage）─────────────────────────────

CREATE TABLE IF NOT EXISTS ts_raw_payloads (
    time          TIMESTAMPTZ NOT NULL,
    mqtt_topic    TEXT NOT NULL,
    payload       JSONB NOT NULL,
    payload_size  INTEGER,
    schema_type_id INTEGER
);

SELECT create_hypertable('ts_raw_payloads', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_raw_topic ON ts_raw_payloads(mqtt_topic, time DESC);
