"""
oee_tool.py — OEE 分析 CLI 工具

從 TimescaleDB 查詢設備狀態，計算並顯示 OEE 報告。

功能：
  - 單一設備 OEE（Availability / Performance / Quality）
  - 全廠 OEE 排名
  - 設備停機 Pareto 分析（停機原因排名）
  - 設備稼動率趨勢

用法：
  # 查看某設備的 OEE
  python oee_tool.py oee --equipment "TaiwanPrecision/Taoyuan/SMT/Line1/Printer" --days 7

  # 全廠 OEE 排名
  python oee_tool.py ranking --days 7

  # 停機 Pareto 分析
  python oee_tool.py downtime --equipment "..." --days 30

  # 設備狀態即時概覽
  python oee_tool.py status

依賴套件：
  pip install psycopg2-binary
"""

import argparse
import json
import os
import sys

import psycopg2


def get_connection(db_url: str):
    return psycopg2.connect(db_url)


# ── 單一設備 OEE ─────────────────────────────────────────────

def cmd_oee(conn, args):
    """計算單一設備的 OEE"""
    cur = conn.cursor()
    cur.execute(
        """WITH state_durations AS (
               SELECT
                   s.tag_id,
                   DATE_TRUNC('day', s.time) AS day,
                   e.state_name,
                   e.state_category,
                   EXTRACT(EPOCH FROM (
                       LEAD(s.time) OVER (PARTITION BY s.tag_id ORDER BY s.time) - s.time
                   )) AS duration_seconds
               FROM ts_status s
               JOIN equipment_state_def e ON s.state_code = e.state_code
               JOIN tags t ON s.tag_id = t.tag_id
               WHERE t.asset_path = %s
                 AND s.state_code IS NOT NULL
                 AND s.time > NOW() - INTERVAL '%s days'
           )
           SELECT
               day::DATE,
               ROUND(SUM(duration_seconds) / 3600.0, 1) AS total_hours,
               ROUND(SUM(duration_seconds) FILTER (WHERE state_category = 'productive') / 3600.0, 1) AS productive_hrs,
               ROUND(SUM(duration_seconds) FILTER (WHERE state_category = 'standby') / 3600.0, 1) AS standby_hrs,
               ROUND(SUM(duration_seconds) FILTER (WHERE state_category = 'down') / 3600.0, 1) AS down_hrs,
               ROUND(100.0 * SUM(duration_seconds) FILTER (WHERE state_category = 'productive')
                     / NULLIF(SUM(duration_seconds) FILTER (WHERE state_category != 'non_scheduled'), 0), 1) AS availability_pct
           FROM state_durations
           WHERE state_category != 'non_scheduled'
           GROUP BY day
           ORDER BY day""",
        (args.equipment, args.days)
    )

    rows = cur.fetchall()
    cur.close()

    if not rows:
        print(f"❌ 無資料: {args.equipment}")
        return

    print("=" * 75)
    print(f"  OEE Report — {args.equipment}")
    print(f"  期間：最近 {args.days} 天")
    print("=" * 75)
    print(f"  {'Date':<12s} {'Total':>6s} {'Prod':>6s} {'Stby':>6s} "
          f"{'Down':>6s} {'Avail%':>8s}")
    print("  " + "-" * 70)

    total_prod = 0
    total_scheduled = 0

    for row in rows:
        day, total, prod, stby, down, avail = row
        prod = prod or 0
        stby = stby or 0
        down = down or 0
        avail = avail or 0

        total_prod += float(prod)
        total_scheduled += float(prod) + float(stby) + float(down)

        bar = "█" * int(avail / 5) if avail else ""
        color = "🟢" if avail >= 85 else "🟡" if avail >= 60 else "🔴"

        print(f"  {str(day):<12s} {total or 0:>5.1f}h {prod:>5.1f}h {stby:>5.1f}h "
              f"{down:>5.1f}h {avail:>7.1f}% {color} {bar}")

    if total_scheduled > 0:
        overall = 100.0 * total_prod / total_scheduled
        print(f"\n  {'Overall':>12s}{'':>25s}"
              f" {overall:>7.1f}%")

    print()


# ── 全廠 OEE 排名 ────────────────────────────────────────────

def cmd_ranking(conn, args):
    """全廠設備 OEE 排名"""
    cur = conn.cursor()
    cur.execute(
        """WITH state_durations AS (
               SELECT
                   t.asset_path,
                   t.display_name,
                   e.state_category,
                   EXTRACT(EPOCH FROM (
                       LEAD(s.time) OVER (PARTITION BY s.tag_id ORDER BY s.time) - s.time
                   )) AS duration_seconds
               FROM ts_status s
               JOIN equipment_state_def e ON s.state_code = e.state_code
               JOIN tags t ON s.tag_id = t.tag_id
               WHERE s.state_code IS NOT NULL
                 AND s.time > NOW() - INTERVAL '%s days'
                 AND t.category = 'Status'
           )
           SELECT
               asset_path,
               display_name,
               ROUND(SUM(duration_seconds) / 3600.0, 1) AS total_hrs,
               ROUND(SUM(duration_seconds) FILTER (WHERE state_category = 'productive') / 3600.0, 1) AS prod_hrs,
               ROUND(SUM(duration_seconds) FILTER (WHERE state_category = 'down') / 3600.0, 1) AS down_hrs,
               ROUND(100.0 * SUM(duration_seconds) FILTER (WHERE state_category = 'productive')
                     / NULLIF(SUM(duration_seconds) FILTER (WHERE state_category != 'non_scheduled'), 0), 1) AS avail_pct
           FROM state_durations
           GROUP BY asset_path, display_name
           ORDER BY avail_pct DESC NULLS LAST""",
        (args.days,)
    )

    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("❌ 無設備狀態資料。")
        return

    print("=" * 85)
    print(f"  全廠 OEE 排名 — 最近 {args.days} 天")
    print("=" * 85)
    print(f"  {'#':>3s} {'Equipment':<35s} {'Prod':>6s} {'Down':>6s} {'Avail%':>8s}")
    print("  " + "-" * 80)

    for i, row in enumerate(rows, 1):
        path, name, total, prod, down, avail = row
        prod = prod or 0
        down = down or 0
        avail = avail or 0

        short = path.split("/")[-1] if path else name
        color = "🟢" if avail >= 85 else "🟡" if avail >= 60 else "🔴"

        print(f"  {i:>3d} {short:<35s} {prod:>5.1f}h {down:>5.1f}h "
              f"{avail:>7.1f}% {color}")

    print()


# ── 停機 Pareto 分析 ─────────────────────────────────────────

def cmd_downtime(conn, args):
    """設備停機原因 Pareto 分析"""
    cur = conn.cursor()

    query = """WITH state_durations AS (
               SELECT
                   e.state_name,
                   e.state_category,
                   e.description,
                   EXTRACT(EPOCH FROM (
                       LEAD(s.time) OVER (PARTITION BY s.tag_id ORDER BY s.time) - s.time
                   )) AS duration_seconds
               FROM ts_status s
               JOIN equipment_state_def e ON s.state_code = e.state_code
               JOIN tags t ON s.tag_id = t.tag_id
               WHERE s.state_code IS NOT NULL
                 AND s.time > NOW() - INTERVAL '%s days'
                 AND e.state_category IN ('down', 'standby')
           """

    params = [args.days]
    if args.equipment:
        query += " AND t.asset_path = %s "
        params.append(args.equipment)

    query += """)
           SELECT
               state_name, description,
               ROUND(SUM(duration_seconds) / 3600.0, 1) AS hours,
               COUNT(*) AS occurrences,
               ROUND(100.0 * SUM(duration_seconds) /
                     NULLIF(SUM(SUM(duration_seconds)) OVER (), 0), 1) AS pct
           FROM state_durations
           WHERE duration_seconds IS NOT NULL
           GROUP BY state_name, description
           ORDER BY hours DESC"""

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("✅ 沒有停機/待機紀錄。")
        return

    equip_label = args.equipment.split("/")[-1] if args.equipment else "全廠"
    print("=" * 70)
    print(f"  停機 Pareto — {equip_label}（最近 {args.days} 天）")
    print("=" * 70)
    print(f"  {'Reason':<25s} {'Desc':<20s} {'Hours':>6s} {'#':>4s} {'%':>6s} Cum")
    print("  " + "-" * 65)

    cumulative = 0
    for row in rows:
        name, desc, hours, occ, pct = row
        hours = hours or 0
        pct = pct or 0
        cumulative += pct
        bar = "█" * int(pct / 3)
        print(f"  {name:<25s} {(desc or '-')[:20]:<20s} {hours:>5.1f}h {occ:>4d} "
              f"{pct:>5.1f}% {bar}")

    print()


# ── 設備狀態即時概覽 ─────────────────────────────────────────

def cmd_status(conn, args):
    """設備即時狀態概覽"""
    cur = conn.cursor()
    cur.execute(
        """SELECT DISTINCT ON (t.asset_path)
               t.asset_path,
               t.display_name,
               e.state_name,
               e.state_category,
               e.color,
               s.time
           FROM ts_status s
           JOIN equipment_state_def e ON s.state_code = e.state_code
           JOIN tags t ON s.tag_id = t.tag_id
           WHERE s.state_code IS NOT NULL
             AND t.category = 'Status'
           ORDER BY t.asset_path, s.time DESC"""
    )

    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("❌ 無設備狀態資料。")
        return

    print("=" * 80)
    print("  設備即時狀態概覽")
    print("=" * 80)

    summary = {"productive": 0, "standby": 0, "down": 0, "non_scheduled": 0}

    for row in rows:
        path, name, state, category, color, time = row
        short = path.split("/")[-1] if path else name
        icon = {"productive": "🟢", "standby": "🟡",
                "down": "🔴", "non_scheduled": "⚪"}.get(category, "⚪")
        summary[category] += 1
        print(f"  {icon} {short:<30s} {state:<22s}  since {time}")

    print()
    total = sum(summary.values())
    print(f"  📊 Total: {total}  |  "
          f"🟢 Productive: {summary['productive']}  |  "
          f"🟡 Standby: {summary['standby']}  |  "
          f"🔴 Down: {summary['down']}  |  "
          f"⚪ Off: {summary['non_scheduled']}")
    print()


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="UNS OEE 分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get(
            "UNS_DB_URL",
            "postgresql://uns_reader:password@localhost:5432/uns_timeseries"
        ),
        help="TimescaleDB 連線字串"
    )

    sub = parser.add_subparsers(dest="command")

    # oee
    p = sub.add_parser("oee", help="單一設備 OEE")
    p.add_argument("--equipment", required=True, help="設備的 asset_path")
    p.add_argument("--days", type=int, default=7)

    # ranking
    p = sub.add_parser("ranking", help="全廠 OEE 排名")
    p.add_argument("--days", type=int, default=7)

    # downtime
    p = sub.add_parser("downtime", help="停機 Pareto 分析")
    p.add_argument("--equipment", help="設備（不指定 = 全廠）")
    p.add_argument("--days", type=int, default=30)

    # status
    sub.add_parser("status", help="設備即時狀態概覽")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    conn = get_connection(args.db_url)

    try:
        {"oee": cmd_oee, "ranking": cmd_ranking,
         "downtime": cmd_downtime, "status": cmd_status
        }[args.command](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
