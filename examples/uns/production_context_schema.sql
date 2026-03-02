-- ═══════════════════════════════════════════════════════════════
-- UNS Production Context Layer — Schema
-- ═══════════════════════════════════════════════════════════════
--
-- 此腳本建立 production_run 表和相關索引，
-- 並修改 ts_telemetry 加上 run_id / lot_id / step_id 欄位，
-- 讓 time-series data 能夠與 MES 生產上下文關聯。
--
-- 執行順序：在 timeseries_schema.sql 之後執行
--   psql -U uns_admin -d uns_timeseries -f production_context_schema.sql
--
-- 設計原則：
--   - production_run 不是 MES Lot Table 的複製品
--   - 它是 time-range index，專門用於 telemetry ↔ lot 的時間關聯
--   - 固定欄位覆蓋 80% 通用需求，JSONB 覆蓋 20% 客製需求
-- ═══════════════════════════════════════════════════════════════


-- ─── 1. Production Run 表 ────────────────────────────────────

CREATE TABLE IF NOT EXISTS production_run (
    run_id          SERIAL PRIMARY KEY,

    -- ── 生產批次識別 ─────────────────────────────────────
    lot_id          TEXT NOT NULL,           -- MES Lot ID
    parent_lot_id   TEXT,                    -- Split 時的母批 ID

    -- ── 設備 ─────────────────────────────────────────────
    equipment_path  TEXT NOT NULL,           -- 對應 tags.asset_path
    chamber_id      TEXT,                    -- 多腔體/多站設備

    -- ── 時間範圍（最重要！time-range JOIN 用） ──────────
    start_time      TIMESTAMPTZ NOT NULL,    -- MES LotMoveIn 時間
    end_time        TIMESTAMPTZ,             -- MES LotMoveOut 時間（NULL = 加工中）

    -- ── Route / Step Context ─────────────────────────────
    step_id         TEXT NOT NULL,
    pass_number     INTEGER DEFAULT 1,       -- 第幾次加工（rework 時 > 1）
    recipe_id       TEXT,
    recipe_version  TEXT,
    product_id      TEXT,

    -- ── 狀態 ─────────────────────────────────────────────
    status          TEXT DEFAULT 'running',   -- running / completed / aborted
    result          TEXT,                     -- pass / fail / rework
    qty_in          INTEGER,                 -- 進站數量
    qty_out         INTEGER,                 -- 出站數量

    -- ── 擴展（不同客戶不同的欄位） ──────────────────────
    -- 半導體：{"wafer_id": "W01", "slot": 3, "reticle_id": "R001"}
    -- 汽車：  {"vin": "1HGCM82633A123456"}
    -- 食品：  {"batch_number": "B2024-001", "expiry": "2024-06-15"}
    context         JSONB,

    -- ── 資料來源追蹤 ─────────────────────────────────────
    source          TEXT DEFAULT 'cdc',      -- cdc / eap / manual
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ─── 2. 索引 ─────────────────────────────────────────────────

-- 最重要的索引：按設備 + 時間範圍查找（Consumer enrichment 用）
CREATE INDEX IF NOT EXISTS idx_run_equipment_time
    ON production_run(equipment_path, start_time DESC);

-- 按 Lot 查完整歷程（EDA 用）
CREATE INDEX IF NOT EXISTS idx_run_lot
    ON production_run(lot_id, start_time);

-- 按 Product + Step 查（SPC 用）
CREATE INDEX IF NOT EXISTS idx_run_product_step
    ON production_run(product_id, step_id);

-- 找目前正在加工的 run（end_time IS NULL）
CREATE INDEX IF NOT EXISTS idx_run_active
    ON production_run(equipment_path)
    WHERE end_time IS NULL;

-- 母批查找（Split/Merge 追溯）
CREATE INDEX IF NOT EXISTS idx_run_parent
    ON production_run(parent_lot_id)
    WHERE parent_lot_id IS NOT NULL;

-- JSONB 索引（客製查詢）
CREATE INDEX IF NOT EXISTS idx_run_context
    ON production_run USING GIN(context);


-- ─── 3. 修改 ts_telemetry：加上生產上下文欄位 ───────────────

-- 加上 run_id（外鍵關聯到 production_run）
ALTER TABLE ts_telemetry
    ADD COLUMN IF NOT EXISTS run_id INTEGER;

-- 加上 lot_id, step_id（反正規化，加速 SPC/EDA 查詢，避免每次都 JOIN）
ALTER TABLE ts_telemetry
    ADD COLUMN IF NOT EXISTS lot_id TEXT;
ALTER TABLE ts_telemetry
    ADD COLUMN IF NOT EXISTS step_id TEXT;

-- 索引：按 lot_id 查（EDA 查 Lot 歷程）
CREATE INDEX IF NOT EXISTS idx_telemetry_lot
    ON ts_telemetry(lot_id, time)
    WHERE lot_id IS NOT NULL;

-- 索引：按 run_id 查（查特定 run 的所有 telemetry）
CREATE INDEX IF NOT EXISTS idx_telemetry_run
    ON ts_telemetry(run_id)
    WHERE run_id IS NOT NULL;


-- ─── 4. 同樣修改其他 ts_* 表 ─────────────────────────────────

-- ts_status
ALTER TABLE ts_status
    ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_status
    ADD COLUMN IF NOT EXISTS lot_id TEXT;

-- ts_alarms
ALTER TABLE ts_alarms
    ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_alarms
    ADD COLUMN IF NOT EXISTS lot_id TEXT;

-- ts_events
ALTER TABLE ts_events
    ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_events
    ADD COLUMN IF NOT EXISTS lot_id TEXT;

-- ts_metrics
ALTER TABLE ts_metrics
    ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE ts_metrics
    ADD COLUMN IF NOT EXISTS lot_id TEXT;


-- ─── 5. 活躍 Run 查詢 View ──────────────────────────────────

CREATE OR REPLACE VIEW active_runs AS
SELECT
    run_id, lot_id, equipment_path, chamber_id,
    step_id, pass_number, recipe_id, product_id,
    start_time, context
FROM production_run
WHERE end_time IS NULL
  AND status = 'running';


-- ─── 6. Lot 完整歷程 View ───────────────────────────────────

CREATE OR REPLACE VIEW lot_history AS
SELECT
    r.lot_id,
    r.parent_lot_id,
    r.step_id,
    r.pass_number,
    r.equipment_path,
    r.chamber_id,
    r.recipe_id,
    r.product_id,
    r.start_time,
    r.end_time,
    r.status,
    r.result,
    r.qty_in,
    r.qty_out,
    EXTRACT(EPOCH FROM (COALESCE(r.end_time, NOW()) - r.start_time)) AS duration_seconds
FROM production_run r
ORDER BY r.lot_id, r.start_time;


-- ─── 7. 驗證 ─────────────────────────────────────────────────

DO $$
BEGIN
    RAISE NOTICE '✅ production_run 表已建立';
    RAISE NOTICE '✅ ts_telemetry 已加上 run_id / lot_id / step_id';
    RAISE NOTICE '✅ active_runs view 已建立';
    RAISE NOTICE '✅ lot_history view 已建立';
END $$;
