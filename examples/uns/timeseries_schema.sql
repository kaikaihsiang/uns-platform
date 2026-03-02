-- =============================================================================
-- UNS Time-Series Database Schema (TimescaleDB / PostgreSQL)
-- =============================================================================
-- 設計原則：
--   1. Tag 的「身份」與「MQTT 來源地址」分離（參考 OSIsoft PI 設計哲學）
--   2. tags 表 = 穩定身份（tag_id 永遠不變，不管 MQTT topic 怎麼改）
--   3. tag_source_mapping 表 = MQTT topic 到 tag 的映射（OT 可以隨時改）
--   4. Category 層是「資產位置」與「資料分類」的分界線
--   5. 每種 Category 各自一張 time-series 表，欄位結構不同
--
-- ERD 概覽：
--
--   tag_source_mapping        tags                 ts_telemetry
--   ┌──────────────────┐     ┌──────────────┐     ┌──────────────┐
--   │ mqtt_topic (來源) │────►│ tag_id (身份) │◄────│ tag_id + time│
--   │ (OT 可以改)       │     │ (永不改變)    │     │ (歷史資料)    │
--   └──────────────────┘     │ display_name │     └──────────────┘
--                            │ category     │
--                            │ unit         │     ts_status / ts_alarms
--                            └──────────────┘     ts_events / ts_metrics
--                                                 (結構同上)
-- =============================================================================


-- ═══════════════════════════════════════════════════════════════
-- 1. Tags 表：資料點的穩定身份
-- ═══════════════════════════════════════════════════════════════
-- tag_id 是永久不變的 identifier，就像 PI Tag 的 Point ID。
-- 即使 MQTT topic 改名、設備搬遷，tag_id 不變，歷史資料不斷。

CREATE TABLE IF NOT EXISTS tags (
    tag_id        SERIAL PRIMARY KEY,

    -- 顯示用名稱（管理員設定，不依賴 MQTT topic）
    display_name  TEXT NOT NULL,             -- '印刷機溫度' / 'Zone1 溫度'

    -- 資產位置（最初從 MQTT topic 解析，後續由管理員維護）
    asset_path    TEXT NOT NULL,             -- 'TaiwanPrecision/Taoyuan/SMT/Line1/Printer'

    -- 資料分類
    category      TEXT NOT NULL,             -- 'Telemetry' / 'Status' / 'Alarm' / ...
    data_point    TEXT,                      -- 'Temperature' / 'MachineState' / NULL

    -- 資料屬性
    unit          TEXT,                      -- '°C' / 'kPa' / 'rpm'
    data_type     TEXT NOT NULL DEFAULT 'float',  -- 'float' / 'string' / 'json'
    description   TEXT,

    -- 追蹤
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_data_at  TIMESTAMPTZ,              -- 最後一筆資料的時間

    UNIQUE(asset_path, category, data_point)
);

CREATE INDEX IF NOT EXISTS idx_tags_asset_path ON tags(asset_path);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS idx_tags_asset_category ON tags(asset_path, category);

-- 可選：PostgreSQL ltree 擴充（更高效的階層查詢）
-- CREATE EXTENSION IF NOT EXISTS ltree;
-- ALTER TABLE tags ADD COLUMN asset_ltree ltree
--     GENERATED ALWAYS AS (replace(asset_path, '/', '.')) STORED;
-- CREATE INDEX IF NOT EXISTS idx_tags_ltree ON tags USING GIST(asset_ltree);


-- ═══════════════════════════════════════════════════════════════
-- 2. Tag Source Mapping：MQTT Topic → Tag 的映射
-- ═══════════════════════════════════════════════════════════════
-- 學 OSIsoft PI 的設計：把「資料來源地址」和「tag 身份」分開。
-- OT 工程師改 PLC/Gateway 的 MQTT topic 設定後，只需更新此表。
-- tag_id 不變，歷史資料不受影響。
--
-- 類比：
--   OSIsoft PI：  Tag Point ID ←→ OPC Server + Item Address
--   UNS：        tag_id       ←→ MQTT Topic

CREATE TABLE IF NOT EXISTS tag_source_mapping (
    mapping_id    SERIAL PRIMARY KEY,
    tag_id        INTEGER NOT NULL REFERENCES tags(tag_id),
    mqtt_topic    TEXT NOT NULL UNIQUE,       -- 目前或歷史的 MQTT topic
    active        BOOLEAN NOT NULL DEFAULT true,
    mapped_at     TIMESTAMPTZ DEFAULT NOW(),
    mapped_by     TEXT,                       -- 誰建立的映射
    notes         TEXT                        -- '自動建立' / '產線改名' / ...
);

CREATE INDEX IF NOT EXISTS idx_mapping_topic ON tag_source_mapping(mqtt_topic) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_mapping_tag ON tag_source_mapping(tag_id);


-- ═══════════════════════════════════════════════════════════════
-- 3. Tag Change Log：變更紀錄（Audit）
-- ═══════════════════════════════════════════════════════════════
-- 記錄所有 topic 變更、tag 合併的歷史，純 audit 用途。

CREATE TABLE IF NOT EXISTS tag_change_log (
    id            SERIAL PRIMARY KEY,
    tag_id        INTEGER NOT NULL REFERENCES tags(tag_id),
    change_type   TEXT NOT NULL,              -- 'remap' / 'merge' / 'rename' / 'create'
    old_value     TEXT,                       -- 舊 topic 或舊 asset_path
    new_value     TEXT,                       -- 新 topic 或新 asset_path
    reason        TEXT,
    changed_at    TIMESTAMPTZ DEFAULT NOW(),
    changed_by    TEXT
);


-- ═══════════════════════════════════════════════════════════════
-- 4. Telemetry 表：數值型感測資料
-- ═══════════════════════════════════════════════════════════════
-- 適合：溫度、壓力、速度、電流...所有 float 型感測值
-- 特性：高頻寫入（每秒~每 100ms），資料量最大

CREATE TABLE IF NOT EXISTS ts_telemetry (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    value       DOUBLE PRECISION NOT NULL,
    quality     TEXT DEFAULT 'good'          -- 'good' / 'uncertain' / 'bad'
);

SELECT create_hypertable('ts_telemetry', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_telemetry_tag ON ts_telemetry(tag_id, time DESC);

-- 資料保留策略（可依需求調整）
-- SELECT add_retention_policy('ts_telemetry', INTERVAL '90 days');

-- 連續聚合（自動降取樣）
-- CREATE MATERIALIZED VIEW ts_telemetry_1min
-- WITH (timescaledb.continuous) AS
-- SELECT time_bucket('1 minute', time) AS bucket,
--        tag_id,
--        AVG(value) AS avg_value,
--        MIN(value) AS min_value,
--        MAX(value) AS max_value,
--        COUNT(*) AS sample_count
-- FROM ts_telemetry
-- GROUP BY bucket, tag_id;


-- ═══════════════════════════════════════════════════════════════
-- 5. Status 表：設備狀態變更紀錄
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ts_status (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    state       TEXT NOT NULL,               -- 'running'/'idle'/'changeover'/'maintenance'/'fault'/'offline'
    sub_state   TEXT,
    mode        TEXT                         -- 'auto' / 'manual' / 'semi_auto'
);

SELECT create_hypertable('ts_status', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_status_tag ON ts_status(tag_id, time DESC);


-- ═══════════════════════════════════════════════════════════════
-- 6. Alarm 表：告警紀錄
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ts_alarms (
    time        TIMESTAMPTZ NOT NULL,
    tag_id      INTEGER NOT NULL REFERENCES tags(tag_id),
    alarm_id    TEXT NOT NULL,
    code        TEXT NOT NULL,
    severity    TEXT NOT NULL,               -- 'info' / 'warning' / 'critical' / 'emergency'
    message     TEXT,
    state       TEXT NOT NULL,               -- 'active' / 'cleared' / 'shelved'
    value       DOUBLE PRECISION,
    threshold   DOUBLE PRECISION
);

SELECT create_hypertable('ts_alarms', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ts_alarms_tag ON ts_alarms(tag_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ts_alarms_severity ON ts_alarms(severity, time DESC);


-- ═══════════════════════════════════════════════════════════════
-- 7. Event 表：製程事件
-- ═══════════════════════════════════════════════════════════════

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


-- ═══════════════════════════════════════════════════════════════
-- 8. Metrics 表：聚合指標
-- ═══════════════════════════════════════════════════════════════

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


-- ═══════════════════════════════════════════════════════════════
-- Tag 管理操作範例
-- ═══════════════════════════════════════════════════════════════

-- [重新映射] OT 改了 MQTT topic（產線改名：Line1 → ProductionLine-A）
-- 步驟：
--   1. 停用所有舊 mapping
--   2. 建立新 mapping 指向同一個 tag_id
--   3. tag_id 不變 → 歷史資料不受影響

-- UPDATE tag_source_mapping
-- SET active = false
-- WHERE mqtt_topic LIKE '%/Line1/%';
--
-- INSERT INTO tag_source_mapping (tag_id, mqtt_topic, mapped_by, notes)
-- SELECT tag_id,
--        replace(mqtt_topic, '/Line1/', '/ProductionLine-A/'),
--        'admin',
--        '產線改名 Line1 → ProductionLine-A'
-- FROM tag_source_mapping
-- WHERE mqtt_topic LIKE '%/Line1/%'
--   AND active = false
--   AND mapped_at = (SELECT MAX(mapped_at) FROM tag_source_mapping sm2
--                    WHERE sm2.tag_id = tag_source_mapping.tag_id AND sm2.active = false);

-- [合併 Tag] OT 先改了 topic，Consumer 自動建了新 tag，事後需要合併
-- 步驟：
--   1. 把 source tag 的所有歷史資料改指向 target tag
--   2. 把 source tag 的 mapping 改指向 target tag
--   3. 刪除 source tag

-- -- 例：tag_id=42（新建的）合併到 tag_id=1（原本的）
-- UPDATE ts_telemetry SET tag_id = 1 WHERE tag_id = 42;
-- UPDATE ts_status    SET tag_id = 1 WHERE tag_id = 42;
-- UPDATE ts_alarms    SET tag_id = 1 WHERE tag_id = 42;
-- UPDATE ts_events    SET tag_id = 1 WHERE tag_id = 42;
-- UPDATE ts_metrics   SET tag_id = 1 WHERE tag_id = 42;
-- UPDATE tag_source_mapping SET tag_id = 1 WHERE tag_id = 42;
-- INSERT INTO tag_change_log (tag_id, change_type, old_value, new_value, reason, changed_by)
-- VALUES (1, 'merge', 'merged tag_id=42', 'into tag_id=1', 'OT 先改了 topic', 'admin');
-- DELETE FROM tags WHERE tag_id = 42;


-- ═══════════════════════════════════════════════════════════════
-- 常用查詢範例
-- ═══════════════════════════════════════════════════════════════

-- [Telemetry] 印刷機溫度，過去 1 小時每分鐘平均
-- SELECT time_bucket('1 minute', t.time) AS minute,
--        AVG(t.value) AS avg_temp
-- FROM ts_telemetry t
-- JOIN tags tg ON t.tag_id = tg.tag_id
-- WHERE tg.asset_path = 'TaiwanPrecision/Taoyuan/SMT/Line1/Printer'
--   AND tg.data_point = 'Temperature'
--   AND t.time > NOW() - INTERVAL '1 hour'
-- GROUP BY minute ORDER BY minute;

-- [Status] Line1 所有設備的當前狀態
-- SELECT tg.asset_path, s.state, s.mode, s.time
-- FROM ts_status s
-- JOIN tags tg ON s.tag_id = tg.tag_id
-- WHERE tg.asset_path LIKE 'TaiwanPrecision/Taoyuan/SMT/Line1/%'
--   AND tg.category = 'Status'
--   AND s.time = (SELECT MAX(time) FROM ts_status WHERE tag_id = s.tag_id);

-- [Alarm] 過去 7 天每天的 critical 告警數
-- SELECT time_bucket('1 day', a.time) AS day,
--        COUNT(*) AS critical_count
-- FROM ts_alarms a
-- WHERE a.severity = 'critical'
--   AND a.state = 'active'
--   AND a.time > NOW() - INTERVAL '7 days'
-- GROUP BY day ORDER BY day;

-- [Metrics] SMT 區過去 30 天 OEE 趨勢
-- SELECT time_bucket('1 day', m.time) AS day,
--        AVG((m.values->>'oee')::float) AS avg_oee
-- FROM ts_metrics m
-- JOIN tags tg ON m.tag_id = tg.tag_id
-- WHERE tg.asset_path LIKE '%/SMT/%'
--   AND m.metric_type = 'OEE'
--   AND m.time > NOW() - INTERVAL '30 days'
-- GROUP BY day ORDER BY day;

-- [跨表] 某設備告警時的溫度是多少？
-- SELECT a.time AS alarm_time, a.code, a.message,
--        (SELECT t.value FROM ts_telemetry t
--         WHERE t.tag_id = temp_tag.tag_id
--           AND t.time <= a.time
--         ORDER BY t.time DESC LIMIT 1) AS temp_at_alarm
-- FROM ts_alarms a
-- JOIN tags atg ON a.tag_id = atg.tag_id
-- JOIN tags temp_tag ON temp_tag.asset_path = atg.asset_path
--                    AND temp_tag.data_point = 'Temperature'
-- WHERE atg.asset_path = 'TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven'
--   AND a.severity = 'critical'
--   AND a.time > NOW() - INTERVAL '24 hours';
