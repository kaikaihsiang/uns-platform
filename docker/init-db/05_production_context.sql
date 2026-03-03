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
