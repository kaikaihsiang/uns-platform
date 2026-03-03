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
    schema_type_id  INTEGER,                     -- FK 在 schema_types 建立後加
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


-- ─── Schema Types ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_types (
    type_id            SERIAL PRIMARY KEY,
    type_name          TEXT NOT NULL UNIQUE,
    decoder            TEXT DEFAULT 'json',
    timestamp_field    TEXT,
    store_raw          BOOLEAN DEFAULT true,
    raw_retention_days INTEGER DEFAULT 30,
    on_schema_mismatch TEXT DEFAULT 'log_and_store',
    on_new_field       TEXT DEFAULT 'suggest',
    fields             JSONB NOT NULL,
    status             TEXT DEFAULT 'confirmed',  -- confirmed / suggested / modified
    version            INTEGER DEFAULT 1,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);


-- ─── 加上 FK ─────────────────────────────────────────────────

ALTER TABLE namespace_nodes
    ADD CONSTRAINT fk_ns_schema_type
    FOREIGN KEY (schema_type_id) REFERENCES schema_types(type_id);
