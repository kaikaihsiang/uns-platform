"""
spc_tool.py — SPC 分析 CLI 工具

從 TimescaleDB 查詢量測資料，產生 SPC 分析報告。

功能：
  - X-bar / R Chart 資料匯出
  - Cpk / Cp 製程能力指數計算
  - OOS (Out of Spec) 趨勢報告
  - 製程-品質關聯分析

用法：
  # 查看某產品某參數的 Cpk
  python spc_tool.py cpk --product Aspirin-500mg --parameter Hardness --days 30

  # 匯出 X-bar chart 資料
  python spc_tool.py xbar --product Aspirin-500mg --parameter Hardness --days 30

  # OOS 趨勢報告
  python spc_tool.py oos --days 90

  # 製程-品質關聯
  python spc_tool.py correlation --product Aspirin-500mg \\
      --process-param OvenTemperature --quality-param Hardness

依賴套件：
  pip install psycopg2-binary
"""

import argparse
import math
import os
import sys

import psycopg2


def get_connection(db_url: str):
    return psycopg2.connect(db_url)


# ── Cpk 計算 ─────────────────────────────────────────────────

def cmd_cpk(conn, args):
    """計算 Cpk 製程能力指數"""
    cur = conn.cursor()
    cur.execute(
        """SELECT
               t.data_point,
               r.product_id,
               COUNT(*) AS n,
               AVG(m.value) AS mean,
               STDDEV(m.value) AS std,
               AVG(m.spec_upper) AS usl,
               AVG(m.spec_lower) AS lsl,
               AVG(m.target_value) AS target
           FROM ts_measurements m
           JOIN tags t ON m.tag_id = t.tag_id
           LEFT JOIN production_run r ON m.run_id = r.run_id
           WHERE t.data_point = %s
             AND m.time > NOW() - INTERVAL '%s days'
             AND m.spec_upper IS NOT NULL
             AND m.spec_lower IS NOT NULL
           """ + ("AND r.product_id = %s " if args.product else "") +
        "GROUP BY t.data_point, r.product_id",
        (args.parameter, args.days) + ((args.product,) if args.product else ())
    )

    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("❌ 無資料。請確認 parameter 名稱和時間範圍。")
        return

    print("=" * 70)
    print(f"  SPC Cpk 報告 — {args.parameter}")
    print(f"  資料範圍：最近 {args.days} 天")
    print("=" * 70)

    for row in rows:
        param, product, n, mean, std, usl, lsl, target = row

        if n < 2 or std is None or std == 0:
            print(f"\n  Product: {product or 'ALL'}")
            print(f"  ⚠ 樣本數不足 (n={n}) 或標準差為 0")
            continue

        mean, std, usl, lsl = float(mean), float(std), float(usl), float(lsl)
        cp = (usl - lsl) / (6 * std)
        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        cpk = min(cpu, cpl)

        judgment = (
            "🟢 Excellent" if cpk >= 1.67 else
            "🟢 Good" if cpk >= 1.33 else
            "🟡 Acceptable" if cpk >= 1.0 else
            "🟠 Poor" if cpk >= 0.67 else
            "🔴 Unacceptable"
        )

        print(f"\n  Product: {product or 'ALL'}")
        print("  ┌─────────────────────────────────────────────┐")
        print(f"  │  n = {n:<8d}                               │")
        print(f"  │  X̄ = {mean:<10.4f}  σ = {std:<10.4f}       │")
        print(f"  │  USL = {usl:<8.2f}  LSL = {lsl:<8.2f}        │")
        print(f"  │  Target = {target or 'N/A':<8}                      │")
        print("  │                                             │")
        print(f"  │  Cp  = {cp:<8.3f}                           │")
        print(f"  │  CPU = {cpu:<8.3f}  CPL = {cpl:<8.3f}        │")
        print(f"  │  Cpk = {cpk:<8.3f}  → {judgment:<20s} │")
        print("  └─────────────────────────────────────────────┘")

    print()


# ── X-bar Chart 資料 ─────────────────────────────────────────

def cmd_xbar(conn, args):
    """匯出 X-bar / R chart 資料"""
    cur = conn.cursor()
    cur.execute(
        """SELECT
               r.lot_id,
               r.start_time::DATE AS production_date,
               COUNT(*) AS n,
               AVG(m.value) AS x_bar,
               STDDEV(m.value) AS std,
               MAX(m.value) - MIN(m.value) AS range_r,
               MIN(m.value) AS min_val,
               MAX(m.value) AS max_val,
               MIN(m.spec_lower) AS lsl,
               MAX(m.spec_upper) AS usl,
               MIN(m.target_value) AS target
           FROM ts_measurements m
           JOIN tags t ON m.tag_id = t.tag_id
           LEFT JOIN production_run r ON m.run_id = r.run_id
           WHERE t.data_point = %s
             AND m.time > NOW() - INTERVAL '%s days'
           """ + ("AND r.product_id = %s " if args.product else "") +
        """GROUP BY r.lot_id, r.start_time::DATE
           ORDER BY r.start_time""",
        (args.parameter, args.days) + ((args.product,) if args.product else ())
    )

    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("❌ 無資料。")
        return

    print("=" * 90)
    print(f"  X-bar / R Chart — {args.parameter}" +
          (f" (Product: {args.product})" if args.product else ""))
    print("=" * 90)
    print(f"  {'Lot':<16s} {'Date':<12s} {'n':>3s} {'X̄':>10s} {'R':>10s} "
          f"{'Min':>10s} {'Max':>10s} {'LSL':>8s} {'USL':>8s}")
    print("  " + "-" * 86)

    for row in rows:
        lot, date, n, xbar, std, rng, mn, mx, lsl, usl, tgt = row
        flag = ""
        if usl and xbar and xbar > usl:
            flag = " 🔴 OOS"
        elif lsl and xbar and xbar < lsl:
            flag = " 🔴 OOS"

        print(f"  {str(lot or '-'):<16s} {str(date):<12s} {n:>3d} "
              f"{xbar:>10.3f} {rng:>10.3f} {mn:>10.3f} {mx:>10.3f} "
              f"{str(lsl or '-'):>8s} {str(usl or '-'):>8s}{flag}")

    print()


# ── OOS 趨勢 ─────────────────────────────────────────────────

def cmd_oos(conn, args):
    """OOS 趨勢報告"""
    cur = conn.cursor()
    cur.execute(
        """SELECT
               r.product_id,
               t.data_point,
               DATE_TRUNC('week', m.time)::DATE AS week,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE m.result = 'oos') AS oos,
               ROUND(100.0 * COUNT(*) FILTER (WHERE m.result = 'oos')
                     / NULLIF(COUNT(*), 0), 2) AS oos_pct
           FROM ts_measurements m
           JOIN tags t ON m.tag_id = t.tag_id
           LEFT JOIN production_run r ON m.run_id = r.run_id
           WHERE m.time > NOW() - INTERVAL '%s days'
           GROUP BY r.product_id, t.data_point, DATE_TRUNC('week', m.time)
           HAVING COUNT(*) FILTER (WHERE m.result = 'oos') > 0
           ORDER BY oos_pct DESC, week DESC""",
        (args.days,)
    )

    rows = cur.fetchall()
    cur.close()

    print("=" * 80)
    print(f"  OOS 趨勢報告 — 最近 {args.days} 天（僅顯示有 OOS 的）")
    print("=" * 80)

    if not rows:
        print("  ✅ 沒有 OOS 紀錄。")
        print()
        return

    print(f"  {'Product':<20s} {'Parameter':<16s} {'Week':<12s} "
          f"{'Total':>6s} {'OOS':>5s} {'Rate':>8s}")
    print("  " + "-" * 75)

    for row in rows:
        product, param, week, total, oos, pct = row
        flag = " 🔴" if pct > 5 else " 🟡" if pct > 1 else ""
        print(f"  {str(product or '-'):<20s} {param:<16s} {str(week):<12s} "
              f"{total:>6d} {oos:>5d} {pct:>7.2f}%{flag}")

    print()


# ── 製程-品質關聯 ─────────────────────────────────────────────

def cmd_correlation(conn, args):
    """製程參數與品質參數的關聯分析"""
    cur = conn.cursor()
    cur.execute(
        """SELECT
               r.lot_id,
               AVG(tel.value) AS avg_process,
               AVG(m.value) AS avg_quality
           FROM production_run r
           JOIN ts_telemetry tel ON tel.run_id = r.run_id
             AND tel.tag_id = (
                 SELECT tag_id FROM tags
                 WHERE data_point = %s LIMIT 1
             )
           JOIN ts_measurements m ON m.run_id = r.run_id
             AND m.tag_id = (
                 SELECT tag_id FROM tags
                 WHERE data_point = %s LIMIT 1
             )
           WHERE r.product_id = %s
             AND r.start_time > NOW() - INTERVAL '%s days'
           GROUP BY r.lot_id
           ORDER BY avg_process""",
        (args.process_param, args.quality_param, args.product, args.days)
    )

    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("❌ 無資料。請確認 product / process-param / quality-param 名稱。")
        return

    print("=" * 60)
    print("  製程-品質關聯分析")
    print(f"  Product:       {args.product}")
    print(f"  製程參數 (X):  {args.process_param}")
    print(f"  品質參數 (Y):  {args.quality_param}")
    print("=" * 60)
    print(f"  {'Lot':<16s} {'Avg Process':>14s} {'Avg Quality':>14s}")
    print("  " + "-" * 50)

    process_vals = []
    quality_vals = []

    for lot, proc, qual in rows:
        proc, qual = float(proc), float(qual)
        process_vals.append(proc)
        quality_vals.append(qual)
        print(f"  {str(lot):<16s} {proc:>14.3f} {qual:>14.3f}")

    # 簡單相關係數
    if len(process_vals) >= 3:
        n = len(process_vals)
        mean_x = sum(process_vals) / n
        mean_y = sum(quality_vals) / n

        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(process_vals, quality_vals)) / n
        std_x = math.sqrt(sum((x - mean_x) ** 2 for x in process_vals) / n)
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in quality_vals) / n)

        if std_x > 0 and std_y > 0:
            r = cov / (std_x * std_y)
            strength = (
                "強正相關" if r > 0.7 else
                "中度正相關" if r > 0.3 else
                "弱/無相關" if r > -0.3 else
                "中度負相關" if r > -0.7 else
                "強負相關"
            )
            print(f"\n  相關係數 r = {r:.4f} → {strength}")

    print()


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="UNS SPC 分析工具",
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

    # cpk
    p = sub.add_parser("cpk", help="計算 Cpk 製程能力指數")
    p.add_argument("--parameter", required=True, help="量測參數名稱")
    p.add_argument("--product", help="產品 ID（可選）")
    p.add_argument("--days", type=int, default=30, help="資料天數")

    # xbar
    p = sub.add_parser("xbar", help="匯出 X-bar / R chart 資料")
    p.add_argument("--parameter", required=True)
    p.add_argument("--product", help="產品 ID（可選）")
    p.add_argument("--days", type=int, default=30)

    # oos
    p = sub.add_parser("oos", help="OOS 趨勢報告")
    p.add_argument("--days", type=int, default=90)

    # correlation
    p = sub.add_parser("correlation", help="製程-品質關聯分析")
    p.add_argument("--product", required=True)
    p.add_argument("--process-param", required=True, help="製程參數名稱")
    p.add_argument("--quality-param", required=True, help="品質參數名稱")
    p.add_argument("--days", type=int, default=90)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    conn = get_connection(args.db_url)

    try:
        {"cpk": cmd_cpk, "xbar": cmd_xbar,
         "oos": cmd_oos, "correlation": cmd_correlation
        }[args.command](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
