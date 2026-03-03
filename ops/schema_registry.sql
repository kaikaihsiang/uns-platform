-- ═══════════════════════════════════════════════════════════════
-- UNS Schema Registry — 表結構
-- ═══════════════════════════════════════════════════════════════
--
-- Schema Registry 用於記錄每個 MQTT topic 的 payload JSON Schema，
-- 支援版本管理 + 相容性檢查。
--
-- 執行方式：
--   psql -U uns_admin -d uns_timeseries -f schema_registry.sql
--
-- 搭配 schema_validator.py 使用。
-- ═══════════════════════════════════════════════════════════════


-- ─── Schema 版本紀錄 ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_registry (
    schema_id       SERIAL PRIMARY KEY,

    -- 哪個 topic pattern 的 schema
    -- 可以是精確 topic 或含 wildcard 的 pattern
    -- 例如：'TaiwanPrecision/+/SMT/+/Printer/Telemetry/Temperature'
    topic_pattern   TEXT NOT NULL,
    category        TEXT NOT NULL,         -- 'Telemetry', 'Status', 'Alarm', ...

    -- 版本
    schema_version  TEXT NOT NULL,         -- Semantic Versioning: '1.0', '1.1', '2.0'

    -- JSON Schema（Draft-07）
    json_schema     JSONB NOT NULL,        -- 完整的 JSON Schema 定義

    -- 相容性
    is_compatible   BOOLEAN DEFAULT true,  -- 與前一版是否向後相容
    breaking_changes TEXT,                 -- 不相容時的變更說明

    -- Metadata
    registered_by   TEXT NOT NULL DEFAULT 'consumer-auto',
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description     TEXT,                  -- 版本說明 / changelog

    -- 唯一約束：同一個 topic pattern 不能有重複的 version
    UNIQUE(topic_pattern, schema_version)
);

-- 查找索引
CREATE INDEX IF NOT EXISTS idx_schema_topic
    ON schema_registry(topic_pattern);

CREATE INDEX IF NOT EXISTS idx_schema_category
    ON schema_registry(category);

CREATE INDEX IF NOT EXISTS idx_schema_registered_at
    ON schema_registry(registered_at DESC);


-- ─── Schema 變更紀錄（Audit） ────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_change_log (
    change_id       SERIAL PRIMARY KEY,
    schema_id       INTEGER REFERENCES schema_registry(schema_id) ON DELETE SET NULL,
    topic_pattern   TEXT NOT NULL,
    old_version     TEXT,                  -- 前一版本
    new_version     TEXT NOT NULL,         -- 新版本
    change_type     TEXT NOT NULL,         -- 'register', 'update', 'deprecate'
    is_compatible   BOOLEAN,
    breaking_changes TEXT,
    changed_by      TEXT NOT NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason          TEXT
);

CREATE INDEX IF NOT EXISTS idx_schema_change_topic
    ON schema_change_log(topic_pattern);


-- ─── 查詢用 View：最新版本 ───────────────────────────────────

CREATE OR REPLACE VIEW schema_latest AS
SELECT DISTINCT ON (topic_pattern)
    schema_id,
    topic_pattern,
    category,
    schema_version,
    json_schema,
    is_compatible,
    registered_by,
    registered_at,
    description
FROM schema_registry
ORDER BY topic_pattern, registered_at DESC;


-- ─── 驗證 ────────────────────────────────────────────────────

DO $$
BEGIN
    RAISE NOTICE '✅ schema_registry 表已建立';
    RAISE NOTICE '✅ schema_change_log 表已建立';
    RAISE NOTICE '✅ schema_latest view 已建立';
END $$;
