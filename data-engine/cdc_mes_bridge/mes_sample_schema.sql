-- =============================================================================
-- MES 範例 Database Schema (PostgreSQL)
-- =============================================================================
-- 此 schema 模擬一個典型的 MES 系統 DB。
-- 注意：這是 MES 自己的 DB，不是 UNS 的 TimescaleDB。
-- Debezium 會監聽這些表的變更，自動發送到 UNS。
-- =============================================================================


-- 需要啟用 PostgreSQL 的邏輯複製（Debezium 必要）
-- ALTER SYSTEM SET wal_level = 'logical';
-- SELECT pg_reload_conf();


-- ═══ 設備主檔 ═══
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id    TEXT PRIMARY KEY,
    equipment_name  TEXT NOT NULL,
    equipment_type  TEXT,                -- 'printer' / 'reflow_oven' / 'aoi' / ...
    line_id         TEXT NOT NULL,       -- 'Line1' / 'Line2'
    area_id         TEXT NOT NULL,       -- 'SMT' / 'Assembly'
    site_id         TEXT DEFAULT 'Taoyuan',
    state           TEXT DEFAULT 'idle', -- 'running' / 'idle' / 'fault' / 'maintenance'
    mode            TEXT DEFAULT 'auto', -- 'auto' / 'manual'
    current_lot     TEXT,
    current_recipe  TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO equipment VALUES
    ('PRN-001', '印刷機-1', 'printer', 'Line1', 'SMT', 'Taoyuan', 'idle', 'auto', NULL, NULL, NOW()),
    ('RFW-001', '迴焊爐-1', 'reflow_oven', 'Line1', 'SMT', 'Taoyuan', 'idle', 'auto', NULL, NULL, NOW()),
    ('AOI-001', 'AOI-1', 'aoi', 'Line1', 'SMT', 'Taoyuan', 'idle', 'auto', NULL, NULL, NOW());


-- ═══ 批次 / Lot 表 ═══
CREATE TABLE IF NOT EXISTS lot (
    lot_id          TEXT PRIMARY KEY,
    work_order      TEXT NOT NULL,
    product_id      TEXT NOT NULL,
    recipe_id       TEXT,
    state           TEXT DEFAULT 'queued',  -- 'queued'/'in_process'/'completed'/'on_hold'
    quantity         INTEGER DEFAULT 0,
    good_qty        INTEGER DEFAULT 0,
    ng_qty          INTEGER DEFAULT 0,
    equipment_id    TEXT,
    line_id         TEXT,
    move_in_time    TIMESTAMPTZ,
    move_out_time   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══ Event Tracking 表（MES 原本就有的） ═══
-- 這張表是 CDC 的主要監聽目標
CREATE TABLE IF NOT EXISTS event_tracking (
    event_id        SERIAL PRIMARY KEY,
    event_code      TEXT NOT NULL,          -- 'lot_move_in' / 'lot_move_out' / 'recipe_change' / ...
    lot_id          TEXT,
    equipment_id    TEXT,
    line_id         TEXT,
    area_id         TEXT,
    operator_id     TEXT,
    result          TEXT,                   -- 'OK' / 'NG' / NULL
    details         JSONB,                  -- 額外資訊
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 建索引：Transform Service 查詢用
CREATE INDEX IF NOT EXISTS idx_event_tracking_time ON event_tracking(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_tracking_type ON event_tracking(event_code);


-- ═══ 配方表 ═══
CREATE TABLE IF NOT EXISTS recipe (
    recipe_id       TEXT PRIMARY KEY,
    recipe_name     TEXT NOT NULL,
    product_id      TEXT NOT NULL,
    version         TEXT DEFAULT '1.0',
    parameters      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO recipe VALUES
    ('RCP-001', 'PCB-A001 迴焊參數', 'PCB-A001', '3.2',
     '{"zone1_temp": 180, "zone2_temp": 220, "zone3_temp": 260, "speed": 0.8}', NOW());


-- ═══ 模擬 MES 交易的 Stored Procedure ═══
-- 實際 MES 中這些是 application code，這裡用 SQL 模擬

CREATE OR REPLACE FUNCTION lot_move_in(
    p_lot_id TEXT,
    p_equipment_id TEXT,
    p_recipe_id TEXT,
    p_operator_id TEXT
) RETURNS TEXT AS $$
DECLARE
    v_line_id TEXT;
    v_area_id TEXT;
BEGIN
    -- 查設備資訊
    SELECT line_id, area_id INTO v_line_id, v_area_id
    FROM equipment WHERE equipment_id = p_equipment_id;

    -- 更新 lot 狀態
    UPDATE lot SET
        state = 'in_process',
        equipment_id = p_equipment_id,
        line_id = v_line_id,
        recipe_id = p_recipe_id,
        move_in_time = NOW(),
        updated_at = NOW()
    WHERE lot_id = p_lot_id;

    -- 更新設備狀態
    UPDATE equipment SET
        state = 'running',
        current_lot = p_lot_id,
        current_recipe = p_recipe_id,
        updated_at = NOW()
    WHERE equipment_id = p_equipment_id;

    -- 寫 event tracking（MES 原本就會做的事）
    INSERT INTO event_tracking (event_code, lot_id, equipment_id, line_id, area_id, operator_id, result)
    VALUES ('lot_move_in', p_lot_id, p_equipment_id, v_line_id, v_area_id, p_operator_id, 'OK');

    RETURN 'OK';
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION lot_move_out(
    p_lot_id TEXT,
    p_good_qty INTEGER,
    p_ng_qty INTEGER,
    p_operator_id TEXT
) RETURNS TEXT AS $$
DECLARE
    v_equipment_id TEXT;
    v_line_id TEXT;
    v_area_id TEXT;
BEGIN
    -- 查 lot 目前在哪台設備
    SELECT equipment_id, line_id INTO v_equipment_id, v_line_id
    FROM lot WHERE lot_id = p_lot_id;

    SELECT area_id INTO v_area_id
    FROM equipment WHERE equipment_id = v_equipment_id;

    -- 更新 lot
    UPDATE lot SET
        state = 'completed',
        good_qty = p_good_qty,
        ng_qty = p_ng_qty,
        move_out_time = NOW(),
        updated_at = NOW()
    WHERE lot_id = p_lot_id;

    -- 更新設備
    UPDATE equipment SET
        state = 'idle',
        current_lot = NULL,
        current_recipe = NULL,
        updated_at = NOW()
    WHERE equipment_id = v_equipment_id;

    -- 寫 event tracking
    INSERT INTO event_tracking (event_code, lot_id, equipment_id, line_id, area_id, operator_id, result, details)
    VALUES ('lot_move_out', p_lot_id, v_equipment_id, v_line_id, v_area_id, p_operator_id, 'OK',
            jsonb_build_object('good_qty', p_good_qty, 'ng_qty', p_ng_qty,
                               'yield', round(p_good_qty::numeric / (p_good_qty + p_ng_qty), 4)));

    RETURN 'OK';
END;
$$ LANGUAGE plpgsql;


-- ═══ 測試用：模擬 MES 交易 ═══
-- INSERT INTO lot VALUES ('LOT-001', 'WO-2024-001', 'PCB-A001', NULL, 'queued', 100, 0, 0, NULL, NULL, NULL, NULL, NOW(), NOW());
-- SELECT lot_move_in('LOT-001', 'PRN-001', 'RCP-001', 'OP-001');
-- SELECT lot_move_out('LOT-001', 98, 2, 'OP-001');
