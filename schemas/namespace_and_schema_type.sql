-- ═══════════════════════════════════════════════════════════════
-- UNS Namespace Nodes + Schema Types — Schema
-- ═══════════════════════════════════════════════════════════════
--
-- 此腳本建立：
--   1. namespace_nodes 表（Namespace Tree 結構，ISA-95 階層）
--   2. schema_types 表（可重用的 payload 結構定義）
--
-- 執行順序：在 timeseries_schema.sql 之前執行（因為其他表可能會參照）
--   psql -U uns_admin -d uns_timeseries -f namespace_and_schema_type.sql
--
-- 參考：platform_system_spec.md §3.2, §5.6
-- ═══════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════
-- 1. Schema Types 表（先建，因為 namespace_nodes 參照它）
-- ═══════════════════════════════════════════════════════════════
-- Schema Type 是可重用的 payload 結構定義，類似 OOP 的 class。
-- 100 台同型設備 → 同一個 Schema Type。

CREATE TABLE IF NOT EXISTS schema_types (
    schema_id          SERIAL PRIMARY KEY,
    schema_name          TEXT NOT NULL UNIQUE,       -- 'SMT_Printer_Telemetry'
    decoder            TEXT DEFAULT 'json',         -- json / sparkplug / text_float / text_csv
    timestamp_field    TEXT,                        -- payload 中的時間戳欄位路徑，如 '$._meta.timestamp'
    store_raw          BOOLEAN DEFAULT true,        -- 是否同時存 raw payload
    raw_retention_days INTEGER DEFAULT 30,
    on_schema_mismatch TEXT DEFAULT 'log_and_store', -- strict / log_and_store / reject
    on_new_field       TEXT DEFAULT 'suggest',       -- auto_create / suggest / ignore

    -- 欄位定義陣列（JSONB）
    -- 每個元素：{name, path, type, unit, extract, persist, deadband, array_mode}
    fields             JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- 版本控制
    version            INTEGER DEFAULT 1,
    status             TEXT DEFAULT 'confirmed',    -- suggested / confirmed / modified

    -- Metadata
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════
-- 2. Namespace Nodes 表
-- ═══════════════════════════════════════════════════════════════
-- Namespace 是一棵樹，遵循 ISA-95 階層。
-- Node 分兩種：structural（階層用）和 topic（對應 MQTT topic）。
-- full_path = MQTT topic（兩者必須一致）。

CREATE TABLE IF NOT EXISTS namespace_nodes (
    node_id         SERIAL PRIMARY KEY,
    parent_id       INTEGER REFERENCES namespace_nodes(node_id),
    name            TEXT NOT NULL,               -- 'Line1', 'Printer', 'Telemetry'
    node_type       TEXT NOT NULL,               -- structural / topic

    -- full_path = MQTT topic path（唯一識別）
    full_path       TEXT NOT NULL UNIQUE,         -- 'Enterprise/Site/Area/Line1/Printer/Telemetry'

    -- Topic Node 專屬（structural node 這些都是 NULL）
    schema_id  INTEGER REFERENCES schema_types(schema_id),
    persist_mode    TEXT DEFAULT 'db',            -- db / retain / passthrough
    retention_days  INTEGER DEFAULT 90,

    -- Metadata
    description     TEXT,
    icon            TEXT,                         -- UI 顯示用
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ                  -- Soft delete
);

CREATE INDEX IF NOT EXISTS idx_ns_parent ON namespace_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_ns_full_path ON namespace_nodes(full_path);
CREATE INDEX IF NOT EXISTS idx_ns_type ON namespace_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_ns_schema ON namespace_nodes(schema_id)
    WHERE schema_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ns_active ON namespace_nodes(node_id)
    WHERE deleted_at IS NULL;


-- ═══════════════════════════════════════════════════════════════
-- 3. 驗證
-- ═══════════════════════════════════════════════════════════════

DO $$
BEGIN
    RAISE NOTICE '✅ schema_types 表已建立';
    RAISE NOTICE '✅ namespace_nodes 表已建立';
END $$;
