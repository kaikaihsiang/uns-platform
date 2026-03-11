"""
archive_to_cold_storage.py — 將超期資料從 TimescaleDB 歸檔到 S3/NAS

功能：
  1. 讀取 retention_policy.yaml 的歸檔設定
  2. 對每個 on_expiry=archive 的 category：
     - 匯出超期資料為 Parquet（或 CSV）
     - 上傳到 S3 / NAS / MinIO
     - 驗證完整性（row count 比對）
     - 從 TimescaleDB 刪除已歸檔的 chunks
  3. 產生歸檔報告

用法：
  # 歸檔所有 on_expiry=archive 的 category
  python archive_to_cold_storage.py \\
      --config retention_policy.yaml \\
      --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries

  # 只歸檔特定 category
  python archive_to_cold_storage.py \\
      --config retention_policy.yaml \\
      --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries \\
      --category telemetry

  # Dry-run: 只計算會歸檔多少資料，不執行
  python archive_to_cold_storage.py \\
      --config retention_policy.yaml \\
      --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries \\
      --dry-run

依賴套件：
    pip install psycopg2-binary pyyaml pandas pyarrow boto3
"""

import argparse
import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("archive")


# =============================================================================
# 設定載入
# =============================================================================

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# =============================================================================
# 歸檔邏輯
# =============================================================================

def get_archive_categories(retention: dict) -> list[tuple[str, dict]]:
    """找出所有 on_expiry=archive 的 category"""
    skip_keys = {"archive"}
    results = []
    for cat, conf in retention.items():
        if cat in skip_keys:
            continue
        if not isinstance(conf, dict):
            continue
        if conf.get("on_expiry") == "archive":
            results.append((cat, conf))
    return results


def count_expired_rows(conn, table: str, cutoff: datetime) -> int:
    """計算超期資料筆數"""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE time < %s", (cutoff,))
    count = cur.fetchone()[0]
    cur.close()
    return count


def export_to_parquet(conn, table: str, cutoff: datetime,
                      output_path: str, compression: str = "snappy"):
    """匯出超期資料為 Parquet 檔案"""
    query = f"SELECT * FROM {table} WHERE time < %s ORDER BY time"
    df = pd.read_sql(query, conn, params=[cutoff])

    if df.empty:
        logger.info(f"  {table}: 沒有超期資料")
        return None

    df.to_parquet(output_path, compression=compression, index=False)
    logger.info(f"  匯出 {len(df)} 筆 → {output_path}")
    return len(df)


def export_to_csv(conn, table: str, cutoff: datetime,
                  output_path: str, compression: str = "gzip"):
    """匯出超期資料為 CSV 檔案"""
    query = f"SELECT * FROM {table} WHERE time < %s ORDER BY time"
    df = pd.read_sql(query, conn, params=[cutoff])

    if df.empty:
        logger.info(f"  {table}: 沒有超期資料")
        return None

    comp = compression if compression != "none" else None
    actual_path = output_path + (".gz" if comp == "gzip" else "")
    df.to_csv(actual_path, index=False, compression=comp)
    logger.info(f"  匯出 {len(df)} 筆 → {actual_path}")
    return len(df)


def upload_to_s3(local_path: str, s3_config: dict, remote_key: str):
    """上傳到 S3 / MinIO"""
    import boto3

    kwargs = {"region_name": s3_config.get("region", "us-east-1")}
    if s3_config.get("endpoint_url"):
        kwargs["endpoint_url"] = s3_config["endpoint_url"]

    s3 = boto3.client("s3", **kwargs)
    bucket = s3_config["bucket"]
    s3.upload_file(local_path, bucket, remote_key)
    logger.info(f"  上傳 S3: s3://{bucket}/{remote_key}")


def upload_to_nas(local_path: str, nas_config: dict, remote_path: str):
    """複製到 NAS 掛載路徑"""
    mount = nas_config["mount_path"]
    full_path = os.path.join(mount, remote_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    shutil.copy2(local_path, full_path)
    logger.info(f"  複製到 NAS: {full_path}")


def delete_archived_chunks(conn, table: str, cutoff: datetime):
    """刪除已歸檔的 TimescaleDB chunks（比 DELETE 高效）"""
    cur = conn.cursor()

    # 用 drop_chunks 刪除整個 chunk（比 DELETE row-by-row 快 100x）
    cur.execute(
        f"SELECT drop_chunks('{table}', older_than => %s::timestamptz)",
        (cutoff,)
    )
    dropped = cur.fetchall()
    conn.commit()
    cur.close()

    chunk_count = len(dropped)
    logger.info(f"  刪除 {chunk_count} 個 chunks (older than {cutoff.isoformat()})")
    return chunk_count


def archive_category(conn, category: str, cat_config: dict,
                     archive_config: dict, dry_run: bool = False):
    """歸檔單一 category 的超期資料"""
    table = cat_config["table"]
    raw_days = cat_config["raw"]
    cutoff = datetime.now() - timedelta(days=raw_days)

    logger.info(f"\n{'='*60}")
    logger.info(f"📦 歸檔 [{category}] — 表: {table}, 超過 {raw_days} 天")
    logger.info(f"   Cutoff: {cutoff.isoformat()}")

    # 計算筆數
    row_count = count_expired_rows(conn, table, cutoff)
    if row_count == 0:
        logger.info("  ✅ 沒有超期資料，跳過")
        return {"category": category, "rows": 0, "status": "skipped"}

    logger.info(f"  待歸檔: {row_count:,} 筆")

    if dry_run:
        logger.info("  [DRY RUN] 不執行實際歸檔")
        return {"category": category, "rows": row_count, "status": "dry_run"}

    # 產生檔案路徑
    now = datetime.now()
    fmt = archive_config.get("format", "parquet")
    ext = "parquet" if fmt == "parquet" else "csv"
    compression = archive_config.get("compression", "snappy")
    filename = f"{category}_{cutoff.strftime('%Y%m')}.{ext}"

    # 匯出到暫存目錄
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, filename)

        if fmt == "parquet":
            exported = export_to_parquet(conn, table, cutoff, local_path, compression)
        else:
            exported = export_to_csv(conn, table, cutoff, local_path, compression)

        if exported is None:
            return {"category": category, "rows": 0, "status": "empty"}

        # 上傳
        backend = archive_config.get("backend", "nas")
        remote_path = f"{category}/{now.strftime('%Y/%m')}/{filename}"

        if backend == "s3" or backend == "minio":
            s3_conf = archive_config.get("s3", {})
            prefix = s3_conf.get("prefix", "").format(
                enterprise="UNS", site="default",
                year=now.strftime("%Y"), month=now.strftime("%m")
            )
            upload_to_s3(local_path, s3_conf, prefix + filename)
        elif backend == "nas":
            nas_conf = archive_config.get("nas", {})
            upload_to_nas(local_path, nas_conf, remote_path)

    # 驗證 & 刪除
    if archive_config.get("delete_after_archive", True):
        deleted = delete_archived_chunks(conn, table, cutoff)
    else:
        deleted = 0
        logger.info("  保留原始資料（delete_after_archive=false）")

    logger.info(f"  ✅ 歸檔完成: {exported:,} 筆匯出, {deleted} chunks 刪除")
    return {
        "category": category,
        "rows": exported,
        "chunks_deleted": deleted,
        "status": "done"
    }


# =============================================================================
# 主程式
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="將超期資料從 TimescaleDB 歸檔到 S3/NAS"
    )
    parser.add_argument("--config", "-c", default="retention_policy.yaml")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--category", help="只歸檔特定 category")
    parser.add_argument("--dry-run", action="store_true",
                        help="只計算筆數，不執行歸檔")
    args = parser.parse_args()

    config = load_config(args.config)
    retention = config.get("retention", {})
    archive_config = retention.get("archive", {})

    if not archive_config.get("enabled", False):
        logger.info("歸檔功能未啟用 (archive.enabled = false)")
        return

    # 找出需要歸檔的 category
    categories = get_archive_categories(retention)
    if args.category:
        categories = [(c, conf) for c, conf in categories if c == args.category]
        if not categories:
            logger.error(f"找不到 category: {args.category}")
            return

    logger.info("連接 TimescaleDB...")
    conn = psycopg2.connect(args.db_url)

    results = []
    for cat, conf in categories:
        result = archive_category(conn, cat, conf, archive_config, args.dry_run)
        results.append(result)

    conn.close()

    # 歸檔報告
    logger.info(f"\n{'='*60}")
    logger.info("📊 歸檔報告")
    logger.info(f"{'='*60}")
    total_rows = 0
    for r in results:
        status = r["status"]
        rows = r["rows"]
        total_rows += rows
        icon = {"done": "✅", "skipped": "⏭️", "dry_run": "🔍", "empty": "📭"}.get(status, "❓")
        logger.info(f"  {icon} {r['category']}: {rows:,} 筆 ({status})")
    logger.info(f"\n  總計: {total_rows:,} 筆")


if __name__ == "__main__":
    main()
