"""
measurement_consumer.py — Measurement Data Consumer 模組

處理 Measurement category 的 payload，寫入 ts_measurements。
支援：
  - 批次多取樣點寫入
  - Spec Limit 自動判定（pass / fail / oos / warning）
  - 與 production_run 關聯
  - SPC 即時 OOS 告警

用法（整合到 consumer_example.py）：

    from measurement_consumer import MeasurementWriter

    meas_writer = MeasurementWriter(db_conn, tag_cache)

    # on_message callback 中
    if category == "Measurement":
        meas_writer.write(topic, msg)

依賴套件：
    pip install psycopg2-binary
"""

import logging
from datetime import datetime
from typing import Optional

from psycopg2.extras import execute_values

logger = logging.getLogger("uns_consumer.measurement")


class MeasurementWriter:
    """
    處理 Measurement payload 並寫入 ts_measurements。

    Measurement payload 結構：
    {
      "_meta": {"category": "Measurement", ...},
      "production_context": {"lot_id": ..., "step_id": ..., ...},
      "data": {
        "measurements": [
          {"parameter": "Hardness", "value": 12.5, "unit": "N",
           "spec_upper": 15.0, "spec_lower": 10.0, "target": 12.0,
           "sample_id": "S001", "sample_position": "head",
           "inspector": "Wang-QC"}
        ]
      }
    }
    """

    def __init__(self, db_conn, tag_cache,
                 enricher=None, metrics=None,
                 oos_callback=None):
        """
        Args:
            db_conn: psycopg2 連線
            tag_cache: TagAdmin 實例（用來取得/建立 tag_id）
            enricher: ContextEnricher 實例（用來取 production_run context）
            metrics: ConsumerMetrics 實例（Prometheus 指標）
            oos_callback: OOS 發生時的回呼函式 fn(lot_id, parameter, value, spec)
        """
        self.db = db_conn
        self.tags = tag_cache
        self.enricher = enricher
        self.metrics = metrics
        self.oos_callback = oos_callback

    def write(self, topic: str, msg: dict) -> dict:
        """
        處理一筆 Measurement payload。

        回傳統計資訊：
            {"total": 3, "pass": 2, "oos": 1, "lot_id": "LOT-001"}
        """
        meta = msg.get("_meta", {})
        ctx = msg.get("production_context", {})
        data = msg.get("data", {})

        equipment_path = meta.get("source", "")
        lot_id = ctx.get("lot_id")
        step_id = ctx.get("step_id")
        measurements = data.get("measurements", [])

        if not measurements:
            logger.warning(f"空的 Measurement payload: {topic}")
            return {"total": 0}

        # 取得 production_run context
        run_id = None
        if self.enricher and lot_id:
            run = self.enricher.get_active_run(equipment_path)
            if run:
                run_id = run["run_id"]

        # 展開每個取樣點
        rows = []
        stats = {"total": 0, "pass": 0, "oos": 0, "fail": 0, "warning": 0}
        oos_items = []

        timestamp = datetime.fromisoformat(
            meta.get("timestamp", datetime.now().isoformat())
        )

        for m in measurements:
            parameter = m.get("parameter", "unknown")
            value = m.get("value")
            unit = m.get("unit")

            if value is None:
                continue

            # 取得或建立 tag_id
            sub_topic = f"{equipment_path}/Measurement/{parameter}"
            parsed = {
                "asset_path": equipment_path,
                "category": "Measurement",
                "data_point": parameter,
            }
            tag_id = self.tags.get_tag_id(sub_topic, parsed, unit=unit)

            # Spec Limit 判定
            spec_upper = m.get("spec_upper")
            spec_lower = m.get("spec_lower")
            target = m.get("target")
            result = self._judge_result(value, spec_upper, spec_lower, target)

            # override if payload already has result
            if "result" in m:
                result = m["result"]

            sample_id = m.get("sample_id")
            sample_position = m.get("sample_position")
            inspector = m.get("inspector")

            rows.append((
                timestamp, tag_id, float(value),
                spec_upper, spec_lower, target,
                result, run_id, lot_id, step_id,
                sample_id, sample_position, inspector,
                None  # context JSONB
            ))

            stats["total"] += 1
            stats[result] = stats.get(result, 0) + 1

            if result == "oos":
                oos_items.append({
                    "parameter": parameter, "value": value,
                    "spec_upper": spec_upper, "spec_lower": spec_lower,
                    "sample_id": sample_id, "lot_id": lot_id,
                })

        # 批次寫入
        if rows:
            cur = self.db.cursor()
            execute_values(
                cur,
                """INSERT INTO ts_measurements
                   (time, tag_id, value, spec_upper, spec_lower, target_value,
                    result, run_id, lot_id, step_id,
                    sample_id, sample_position, inspector, context)
                   VALUES %s""",
                rows,
                page_size=100
            )
            self.db.commit()
            cur.close()

        # OOS 回呼（告警用）
        if oos_items and self.oos_callback:
            for item in oos_items:
                try:
                    self.oos_callback(
                        lot_id=item["lot_id"],
                        parameter=item["parameter"],
                        value=item["value"],
                        spec={"upper": item["spec_upper"],
                              "lower": item["spec_lower"]},
                    )
                except Exception as e:
                    logger.error(f"OOS callback 執行失敗: {e}")

        stats["lot_id"] = lot_id
        logger.info(
            f"Measurement: {lot_id} @ {equipment_path} "
            f"→ {stats['total']} 筆 (pass={stats['pass']}, "
            f"oos={stats['oos']}, fail={stats['fail']})"
        )

        return stats

    @staticmethod
    def _judge_result(value: float,
                      spec_upper: Optional[float],
                      spec_lower: Optional[float],
                      target: Optional[float]) -> str:
        """
        根據 Spec Limit 判定量測結果。

        規則：
          - 超出 USL 或 LSL → oos (Out of Spec)
          - 在 Spec 內但偏離 target 超過 50% range → warning
          - 其他 → pass
        """
        if spec_upper is not None and value > spec_upper:
            return "oos"
        if spec_lower is not None and value < spec_lower:
            return "oos"

        # Warning: 偏離 target 超過 spec range 的 75%
        if target is not None and spec_upper is not None and spec_lower is not None:
            spec_range = spec_upper - spec_lower
            if spec_range > 0:
                deviation = abs(value - target) / spec_range
                if deviation > 0.375:  # 75% of half range
                    return "warning"

        return "pass"

    def calculate_cpk(self, tag_id: int, days: int = 30) -> Optional[dict]:
        """
        計算某量測項目的 Cpk（製程能力指數）。

        Cpk = min(CPU, CPL) where:
          CPU = (USL - X̄) / (3σ)
          CPL = (X̄ - LSL) / (3σ)

        Returns:
            {"cpk": 1.33, "cp": 1.5, "mean": 12.1, "std": 0.3,
             "usl": 15.0, "lsl": 10.0, "sample_count": 100}
        """
        cur = self.db.cursor()
        cur.execute(
            """SELECT AVG(value), STDDEV(value), COUNT(*),
                      AVG(spec_upper), AVG(spec_lower)
               FROM ts_measurements
               WHERE tag_id = %s
                 AND time > NOW() - INTERVAL '%s days'
                 AND spec_upper IS NOT NULL
                 AND spec_lower IS NOT NULL""",
            (tag_id, days)
        )
        row = cur.fetchone()
        cur.close()

        if not row or row[2] < 2 or row[1] is None or row[1] == 0:
            return None

        mean, std, count = float(row[0]), float(row[1]), int(row[2])
        usl, lsl = float(row[3]), float(row[4])

        cp = (usl - lsl) / (6 * std)
        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        cpk = min(cpu, cpl)

        return {
            "cpk": round(cpk, 3),
            "cp": round(cp, 3),
            "cpu": round(cpu, 3),
            "cpl": round(cpl, 3),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "usl": usl,
            "lsl": lsl,
            "sample_count": count,
            "judgment": (
                "Excellent" if cpk >= 1.67 else
                "Good" if cpk >= 1.33 else
                "Acceptable" if cpk >= 1.0 else
                "Poor" if cpk >= 0.67 else
                "Unacceptable"
            )
        }
