-- ═══════════════════════════════════════════════════════════════
-- UNS Raw Payloads — Schema (TimescaleDB Hypertable)
-- ═══════════════════════════════════════════════════════════════
--
-- Dual Storage 的 Raw 端：整包 MQTT payload 原封不動存。
-- 用途：backfill、除錯、schema 修正後重新 extract。
-- 預設 retention 30 天（短於 extracted data）。
--
-- 執行順序：在 namespace_and_schema_type.sql 之後
--   psql -U uns_admin -d uns_timeseries -f raw_payloads_schema.sql
--
-- 參考：platform_system_spec.md §6.2
-- ═══════════════════════════════════════════════════════════════


CREATE TABLE IF NOT EXISTS ts_raw_payloads (
    time             TIMESTAMPTZ NOT NULL,
    topic            TEXT NOT NULL,               -- MQTT topic（= namespace_nodes.full_path）
    payload          JSONB NOT NULL,              -- 整包原始 payload
    schema_type_id   INTEGER,                     -- 當時綁定的 Schema Type（可為 NULL）
    node_id          INTEGER,                     -- 對應的 namespace node（可為 NULL）
    payload_size     INTEGER                      -- payload 大小（bytes），監控用
);

SELECT create_hypertable('ts_raw_payloads', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => true
);

CREATE INDEX IF NOT EXISTS idx_raw_topic_time
    ON ts_raw_payloads(topic, time DESC);

CREATE INDEX IF NOT EXISTS idx_raw_schema_type
    ON ts_raw_payloads(schema_type_id, time DESC)
    WHERE schema_type_id IS NOT NULL;

-- 預設 30 天 retention（可依需求調整）
-- SELECT add_retention_policy('ts_raw_payloads', INTERVAL '30 days');


-- ═══════════════════════════════════════════════════════════════
-- 驗證
-- ═══════════════════════════════════════════════════════════════

DO $$
BEGIN
    RAISE NOTICE '✅ ts_raw_payloads hypertable 已建立';
END $$;
