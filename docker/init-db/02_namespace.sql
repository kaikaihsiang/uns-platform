-- =============================================================================
-- 02: Namespace Nodes + Schema Types
-- =============================================================================
-- 來源：platform_system_spec.md §3.2, §5.6

-- ─── Namespace Nodes ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS namespace_nodes (
    node_id         SERIAL PRIMARY KEY,
    parent_id       INTEGER REFERENCES namespace_nodes(node_id),
    name            TEXT NOT NULL,
    node_type       TEXT NOT NULL,               -- structural / topic
    full_path       TEXT NOT NULL UNIQUE,

    -- Topic Node 專屬
    schema_id       INTEGER,                     -- FK 在 uns_payload_schemas 建立後加
    persist_mode    TEXT DEFAULT 'db',            -- db / retain / passthrough
    retention_days  INTEGER DEFAULT 90,

    -- Metadata
    description     TEXT,
    icon            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ                  -- Soft delete
);

CREATE INDEX IF NOT EXISTS idx_ns_parent ON namespace_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_ns_path ON namespace_nodes(full_path);
CREATE INDEX IF NOT EXISTS idx_ns_type ON namespace_nodes(node_type);

COMMENT ON COLUMN namespace_nodes.node_type IS '節點類型: structural (階層) / topic (資料點)';
COMMENT ON COLUMN namespace_nodes.full_path IS '完整 MQTT Topic 路徑';
COMMENT ON COLUMN namespace_nodes.persist_mode IS '持久化模式: db (存庫) / retain (僅保留最新) / passthrough (僅轉發)';


-- ─── Payload Schemas ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS uns_payload_schemas (
    schema_id          SERIAL PRIMARY KEY,
    schema_name        TEXT NOT NULL UNIQUE,
    schema_category    TEXT NOT NULL DEFAULT 'telemetry',
    decoder            TEXT DEFAULT 'json',
    timestamp_field    TEXT,
    store_raw          BOOLEAN DEFAULT true,
    raw_retention_days INTEGER DEFAULT 30,
    on_schema_mismatch TEXT DEFAULT 'log_and_store',
    on_new_field       TEXT DEFAULT 'suggest',
    fields             JSONB NOT NULL,
    status             TEXT DEFAULT 'confirmed',  -- confirmed / suggested / modified
    is_suggested       BOOLEAN DEFAULT false,
    topic_pattern      TEXT,
    version            INTEGER DEFAULT 1,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW(),
    deleted_at         TIMESTAMPTZ
);

COMMENT ON TABLE uns_payload_schemas IS '定義 MQTT Payload 的解析規則與分類路由';
COMMENT ON COLUMN uns_payload_schemas.schema_category IS '資料分類: telemetry, status, alarm, event, measurement, metrics';
COMMENT ON COLUMN uns_payload_schemas.fields IS 'JSONPath 提取規則陣列';


-- ─── 加上 FK ─────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ns_schema') THEN
        ALTER TABLE namespace_nodes
            ADD CONSTRAINT fk_ns_schema
            FOREIGN KEY (schema_id) REFERENCES uns_payload_schemas(schema_id);
    END IF;
END $$;
