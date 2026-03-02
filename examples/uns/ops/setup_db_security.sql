-- ═══════════════════════════════════════════════════════════════
-- UNS TimescaleDB — 安全性設定（角色 + 權限 + SSL）
-- ═══════════════════════════════════════════════════════════════
--
-- 此腳本建立 3 個不同權限的 DB role，實現最小權限原則：
--   uns_writer  — Consumer 寫入用（INSERT only）
--   uns_reader  — Data Access Service 查詢用（SELECT only）
--   uns_admin   — 管理操作用（TagAdmin, schema migration）
--
-- 執行方式（需要 superuser 權限）：
--   psql -U postgres -d uns_timeseries -f setup_db_security.sql
--
-- ⚠ 請將密碼替換為實際的安全密碼！
-- ═══════════════════════════════════════════════════════════════


-- ─── 1. 建立 Role ────────────────────────────────────────────

-- 先刪除（冪等）
DO $$
BEGIN
    -- 避免 "role already exists" 錯誤
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'uns_writer') THEN
        -- 先撤銷所有現有權限，才能 DROP
        REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM uns_writer;
        REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM uns_writer;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'uns_reader') THEN
        REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM uns_reader;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'uns_admin') THEN
        REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM uns_admin;
        REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM uns_admin;
    END IF;
END $$;

-- 建立 role（如已存在則只更新密碼）
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'uns_writer') THEN
        CREATE ROLE uns_writer LOGIN PASSWORD 'CHANGE_ME_writer_password';
    ELSE
        ALTER ROLE uns_writer WITH PASSWORD 'CHANGE_ME_writer_password';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'uns_reader') THEN
        CREATE ROLE uns_reader LOGIN PASSWORD 'CHANGE_ME_reader_password';
    ELSE
        ALTER ROLE uns_reader WITH PASSWORD 'CHANGE_ME_reader_password';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'uns_admin') THEN
        CREATE ROLE uns_admin LOGIN PASSWORD 'CHANGE_ME_admin_password';
    ELSE
        ALTER ROLE uns_admin WITH PASSWORD 'CHANGE_ME_admin_password';
    END IF;
END $$;


-- ─── 2. uns_writer：Consumer 寫入用 ─────────────────────────
-- 只能 INSERT time-series 資料
-- 可以 SELECT/INSERT/UPDATE tags 和 mapping（Consumer 自動建 tag 用）

GRANT CONNECT ON DATABASE uns_timeseries TO uns_writer;
GRANT USAGE ON SCHEMA public TO uns_writer;

-- Time-series 表：只能 INSERT
GRANT INSERT ON ts_telemetry TO uns_writer;
GRANT INSERT ON ts_status    TO uns_writer;
GRANT INSERT ON ts_alarms    TO uns_writer;
GRANT INSERT ON ts_events    TO uns_writer;
GRANT INSERT ON ts_metrics   TO uns_writer;

-- Tag 管理表：Consumer 需要查找 + 自動建立 tag
GRANT SELECT, INSERT, UPDATE ON tags              TO uns_writer;
GRANT SELECT, INSERT, UPDATE ON tag_source_mapping TO uns_writer;
GRANT SELECT, INSERT         ON tag_change_log     TO uns_writer;

-- Sequence（auto-increment tag_id 用）
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO uns_writer;

-- 未來新建的表也自動授權（可選）
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT INSERT ON TABLES TO uns_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO uns_writer;


-- ─── 3. uns_reader：Data Access Service 查詢用 ──────────────
-- 只能 SELECT（任何表都可以，包括 Continuous Aggregate Views）

GRANT CONNECT ON DATABASE uns_timeseries TO uns_reader;
GRANT USAGE ON SCHEMA public TO uns_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO uns_reader;

-- 未來新建的表也自動授權
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO uns_reader;


-- ─── 4. uns_admin：管理操作用 ────────────────────────────────
-- TagAdmin 的 remap/merge/delete 操作需要完整權限

GRANT CONNECT ON DATABASE uns_timeseries TO uns_admin;
GRANT USAGE ON SCHEMA public TO uns_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO uns_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO uns_admin;

-- 未來新建的表也自動授權
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO uns_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO uns_admin;


-- ─── 5. SSL 連線設定 ─────────────────────────────────────────
-- 以下設定需要修改 postgresql.conf 和 pg_hba.conf

-- postgresql.conf 設定（需手動修改）：
--   ssl = on
--   ssl_cert_file = '/var/lib/postgresql/certs/server.crt'
--   ssl_key_file  = '/var/lib/postgresql/certs/server.key'
--   ssl_ca_file   = '/var/lib/postgresql/certs/ca.crt'

-- pg_hba.conf 設定（強制 SSL 連線）：
--   # 拒絕所有非 SSL 的遠端連線
--   hostnossl  all  all  0.0.0.0/0  reject
--   # 只允許 SSL 連線
--   hostssl    uns_timeseries  uns_writer  10.0.0.0/8   scram-sha-256
--   hostssl    uns_timeseries  uns_reader  10.0.0.0/8   scram-sha-256
--   hostssl    uns_timeseries  uns_admin   10.0.0.0/8   scram-sha-256
--   # Localhost 允許非 SSL（開發用）
--   host       all             all         127.0.0.1/32 scram-sha-256


-- ─── 6. 驗證 ────────────────────────────────────────────────

-- 驗證 role 是否建立成功
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('uns_writer', 'uns_reader', 'uns_admin')
    LOOP
        RAISE NOTICE '✅ Role 存在: %', r.rolname;
    END LOOP;
END $$;

-- 驗證權限（可用以下 SQL 查看）：
-- SELECT grantee, table_name, privilege_type
-- FROM information_schema.table_privileges
-- WHERE grantee IN ('uns_writer', 'uns_reader', 'uns_admin')
-- ORDER BY grantee, table_name;
