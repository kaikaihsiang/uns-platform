"""
apply_retention.py — 從 retention_policy.yaml 自動套用 TimescaleDB 保留策略

功能：
  1. 讀取 retention_policy.yaml
  2. 對每個 category 的 hypertable 設定 retention policy
  3. 建立 Continuous Aggregate（降取樣）view
  4. 設定 Continuous Aggregate 的自動刷新 policy
  5. 對降取樣 view 也設定 retention policy

特性：
  - 冪等操作：重複執行不會出錯（先移除舊 policy 再建新的）
  - Dry-run 模式：加 --dry-run 只印 SQL 不執行
  - 只更新有變動的 policy

用法：
  # 正式執行
  python apply_retention.py \\
      --config retention_policy.yaml \\
      --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries

  # 只印 SQL，不執行
  python apply_retention.py \\
      --config retention_policy.yaml \\
      --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries \\
      --dry-run

依賴套件：
    pip install psycopg2-binary pyyaml
"""

import argparse
import logging
import sys

import psycopg2
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("apply_retention")


# =============================================================================
# SQL 產生器
# =============================================================================

def generate_retention_sql(category: str, config: dict) -> list[dict]:
    """
    根據 category 設定，產生需要執行的 SQL 列表。

    回傳 list of {"description": str, "sql": str}
    """
    statements = []
    table = config["table"]
    raw_days = config["raw"]

    # --- 1. 移除舊的 retention policy（冪等） ---
    statements.append({
        "description": f"[{category}] 移除舊的 retention policy（如有）",
        "sql": f"SELECT remove_retention_policy('{table}', if_exists => true);"
    })

    # --- 2. 建立新的 retention policy ---
    statements.append({
        "description": f"[{category}] 設定 raw 資料保留 {raw_days} 天",
        "sql": f"SELECT add_retention_policy('{table}', INTERVAL '{raw_days} days');"
    })

    # --- 3. Continuous Aggregate（降取樣） ---
    downsampled = config.get("downsampled") or []
    for ds in downsampled:
        view_name = ds["view_name"]
        interval = ds["interval"]
        retention = ds["retention"]
        refresh_interval = ds["refresh_interval"]
        start_offset = ds["refresh_start_offset"]
        end_offset = ds["refresh_end_offset"]
        source = ds.get("source", table)  # 預設從原始表，cascade 時從上一層 view

        # 判斷聚合 columns（根據 source 決定）
        if source == table:
            # 從原始表聚合
            agg_select = f"""
    time_bucket('{interval}', time) AS bucket,
    tag_id,
    AVG(value)   AS avg_value,
    MIN(value)   AS min_value,
    MAX(value)   AS max_value,
    COUNT(*)     AS sample_count"""
            group_by = "bucket, tag_id"
        else:
            # 從上一層 view 再聚合（cascade）
            agg_select = f"""
    time_bucket('{interval}', bucket) AS bucket,
    tag_id,
    AVG(avg_value)     AS avg_value,
    MIN(min_value)     AS min_value,
    MAX(max_value)     AS max_value,
    SUM(sample_count)  AS sample_count"""
            group_by = f"time_bucket('{interval}', bucket), tag_id"

        # 先 DROP（冪等）
        statements.append({
            "description": f"[{category}] 移除舊的 Continuous Aggregate: {view_name}",
            "sql": f"DROP MATERIALIZED VIEW IF EXISTS {view_name} CASCADE;"
        })

        # CREATE MATERIALIZED VIEW
        statements.append({
            "description": f"[{category}] 建立 Continuous Aggregate: {view_name} ({interval})",
            "sql": f"""CREATE MATERIALIZED VIEW {view_name}
WITH (timescaledb.continuous) AS
SELECT{agg_select}
FROM {source}
GROUP BY {group_by}
WITH NO DATA;"""
        })

        # 自動刷新 policy
        statements.append({
            "description": f"[{category}] 設定 {view_name} 自動刷新 (每 {refresh_interval})",
            "sql": f"""SELECT add_continuous_aggregate_policy('{view_name}',
    start_offset    => INTERVAL '{start_offset}',
    end_offset      => INTERVAL '{end_offset}',
    schedule_interval => INTERVAL '{refresh_interval}');"""
        })

        # 降取樣 view 的 retention policy
        statements.append({
            "description": f"[{category}] 設定 {view_name} 保留 {retention} 天",
            "sql": f"SELECT add_retention_policy('{view_name}', INTERVAL '{retention} days');"
        })

    return statements


# =============================================================================
# 主程式
# =============================================================================

def load_config(path: str) -> dict:
    """載入 retention_policy.yaml"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply(db_url: str, config_path: str, dry_run: bool = False):
    """讀取設定檔，套用所有 retention policy"""

    config = load_config(config_path)
    retention = config.get("retention", {})

    # 收集所有 category 的 SQL（排除 archive 設定）
    all_statements = []
    skip_keys = {"archive"}

    for category, cat_config in retention.items():
        if category in skip_keys:
            continue
        if not isinstance(cat_config, dict) or "table" not in cat_config:
            logger.warning(f"跳過無效的 category: {category}")
            continue

        stmts = generate_retention_sql(category, cat_config)
        all_statements.extend(stmts)

    if not all_statements:
        logger.warning("沒有需要執行的 SQL")
        return

    # Dry-run：只印 SQL
    if dry_run:
        logger.info(f"=== DRY RUN（共 {len(all_statements)} 條 SQL）===\n")
        for stmt in all_statements:
            print(f"-- {stmt['description']}")
            print(stmt["sql"])
            print()
        return

    # 正式執行
    logger.info(f"連接 TimescaleDB: {db_url.split('@')[-1]}")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    success = 0
    failed = 0

    for stmt in all_statements:
        try:
            logger.info(stmt["description"])
            cur.execute(stmt["sql"])
            success += 1
        except Exception as e:
            logger.error(f"  ❌ 失敗: {e}")
            failed += 1

    cur.close()
    conn.close()

    logger.info(f"\n完成！成功: {success}, 失敗: {failed}")

    if failed > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="從 retention_policy.yaml 自動套用 TimescaleDB 保留策略"
    )
    parser.add_argument(
        "--config", "-c",
        default="retention_policy.yaml",
        help="retention_policy.yaml 路徑 (預設: retention_policy.yaml)"
    )
    parser.add_argument(
        "--db-url",
        required=True,
        help="TimescaleDB 連線字串，如 postgresql://uns_admin:pwd@localhost:5432/uns_timeseries"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只印 SQL，不實際執行"
    )
    args = parser.parse_args()

    apply(
        db_url=args.db_url,
        config_path=args.config,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
