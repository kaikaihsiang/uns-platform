"""
production_context_consumer.py — 雙模式 Production Context Consumer

支援兩種資料收集模式：
  模式 A（Continuous）：設備固定間隔上傳，Consumer 查 production_run 補上下文
  模式 B（Commanded）：EAP 帶著完整 lot/recipe context 上傳，Consumer 直接寫入

此模組提供：
  1. ProductionRunCache — 快取目前各設備的 active run（避免每筆 telemetry 都查 DB）
  2. TraceDataWriter   — 處理 EAP 的批次 trace data（模式 B）
  3. ContextEnricher   — 包裝整個 enrichment 流程

用法（整合到 consumer_example.py）：

    from production_context_consumer import ContextEnricher

    enricher = ContextEnricher(db_conn)

    # 在 TimeSeriesWriter.write() 中使用
    def write(self, topic, payload_bytes):
        msg = json.loads(payload_bytes)
        meta = msg.get("_meta", {})
        mode = meta.get("collection_mode", "continuous")

        if mode == "commanded":
            enricher.write_commanded(topic, msg)
        else:
            run = enricher.get_active_run(equipment_path)
            enricher.write_continuous(topic, msg, run)

依賴套件：
    pip install psycopg2-binary
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import Json, execute_values

logger = logging.getLogger("uns_consumer.production_context")


# =============================================================================
# 1. Production Run Cache
# =============================================================================

class ProductionRunCache:
    """
    快取目前各設備的 active run（end_time IS NULL）。

    模式 A 的 Consumer 每收到一筆 telemetry 就需要知道「這台設備目前在加工什麼」。
    不可能每筆都查 DB，所以在記憶體中維護一份快取。

    更新時機：
      - 啟動時載入所有 active runs
      - 收到 MES LotMoveIn 事件 → 加入新 run
      - 收到 MES LotMoveOut 事件 → 關閉該 run
      - 每 N 秒從 DB 重新同步一次（防止快取和 DB 不一致）
    """

    def __init__(self, db_conn, sync_interval_seconds: int = 60):
        self.db = db_conn
        self.sync_interval = sync_interval_seconds
        self.last_sync = None

        # equipment_path → active run dict
        # 多腔體設備用 "equipment_path:chamber_id" 作為 key
        self.cache: dict[str, dict] = {}

        self._load_active_runs()

    def _load_active_runs(self):
        """從 DB 載入所有 active runs"""
        cur = self.db.cursor()
        cur.execute(
            """SELECT run_id, lot_id, equipment_path, chamber_id,
                      step_id, pass_number, recipe_id, product_id,
                      start_time, context
               FROM production_run
               WHERE end_time IS NULL AND status = 'running'"""
        )
        self.cache.clear()
        for row in cur.fetchall():
            run = {
                "run_id": row[0], "lot_id": row[1],
                "equipment_path": row[2], "chamber_id": row[3],
                "step_id": row[4], "pass_number": row[5],
                "recipe_id": row[6], "product_id": row[7],
                "start_time": row[8], "context": row[9],
            }
            key = self._make_key(run["equipment_path"], run["chamber_id"])
            self.cache[key] = run
        cur.close()
        self.last_sync = datetime.now()
        logger.info(f"已載入 {len(self.cache)} 個 active production runs")

    def _make_key(self, equipment_path: str, chamber_id: str = None) -> str:
        if chamber_id:
            return f"{equipment_path}:{chamber_id}"
        return equipment_path

    def get_active_run(self, equipment_path: str,
                       chamber_id: str = None) -> Optional[dict]:
        """
        查找設備目前的 active run。

        回傳 None 表示此設備目前沒有在加工（idle）。
        """
        # 定期同步
        if (self.last_sync and
            datetime.now() - self.last_sync > timedelta(seconds=self.sync_interval)):
            self._load_active_runs()

        key = self._make_key(equipment_path, chamber_id)
        return self.cache.get(key)

    def on_lot_move_in(self, event: dict):
        """
        收到 MES LotMoveIn 事件時呼叫。

        建立新的 production_run 紀錄 + 更新快取。
        event 來自 CDC Transform 或直接的 MES 通知。
        """
        cur = self.db.cursor()

        # 檢查是否 rework（同 lot + step 已存在）
        cur.execute(
            """SELECT MAX(pass_number) FROM production_run
               WHERE lot_id = %s AND step_id = %s AND equipment_path = %s""",
            (event["lot_id"], event["step_id"], event["equipment_path"])
        )
        row = cur.fetchone()
        pass_number = (row[0] or 0) + 1

        # 建立 run
        cur.execute(
            """INSERT INTO production_run
               (lot_id, parent_lot_id, equipment_path, chamber_id,
                start_time, step_id, pass_number,
                recipe_id, recipe_version, product_id,
                qty_in, context, source)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING run_id""",
            (event["lot_id"], event.get("parent_lot_id"),
             event["equipment_path"], event.get("chamber_id"),
             event["timestamp"], event["step_id"], pass_number,
             event.get("recipe_id"), event.get("recipe_version"),
             event.get("product_id"),
             event.get("qty_in"),
             Json(event.get("context")) if event.get("context") else None,
             event.get("source", "cdc"))
        )
        run_id = cur.fetchone()[0]
        self.db.commit()
        cur.close()

        # 更新快取
        run = {
            "run_id": run_id, "lot_id": event["lot_id"],
            "equipment_path": event["equipment_path"],
            "chamber_id": event.get("chamber_id"),
            "step_id": event["step_id"], "pass_number": pass_number,
            "recipe_id": event.get("recipe_id"),
            "product_id": event.get("product_id"),
            "start_time": event["timestamp"],
            "context": event.get("context"),
        }
        key = self._make_key(event["equipment_path"], event.get("chamber_id"))
        self.cache[key] = run

        logger.info(
            f"LotMoveIn: {event['lot_id']} @ {event['equipment_path']} "
            f"step={event['step_id']} pass={pass_number} → run_id={run_id}"
        )
        return run_id

    def on_lot_move_out(self, event: dict):
        """
        收到 MES LotMoveOut 事件時呼叫。

        關閉 production_run 紀錄 + 從快取中移除。
        """
        key = self._make_key(event["equipment_path"], event.get("chamber_id"))
        run = self.cache.get(key)

        if not run:
            logger.warning(
                f"LotMoveOut 但找不到 active run: "
                f"{event['lot_id']} @ {event['equipment_path']}"
            )
            return

        cur = self.db.cursor()
        cur.execute(
            """UPDATE production_run
               SET end_time = %s, status = 'completed',
                   result = %s, qty_out = %s
               WHERE run_id = %s""",
            (event["timestamp"], event.get("result", "pass"),
             event.get("qty_out"), run["run_id"])
        )
        self.db.commit()
        cur.close()

        # 從快取中移除
        del self.cache[key]

        logger.info(
            f"LotMoveOut: {event['lot_id']} @ {event['equipment_path']} "
            f"run_id={run['run_id']}"
        )


# =============================================================================
# 2. Trace Data Writer（模式 B：指令式收集）
# =============================================================================

class TraceDataWriter:
    """
    處理 EAP 風格的批次 trace data。

    EAP payload 包含一整段加工的所有取樣點（數百甚至數千筆），
    需要展開成 ts_telemetry 的多筆 INSERT。
    """

    def __init__(self, db_conn, tag_cache):
        self.db = db_conn
        self.tags = tag_cache

    def write_commanded_payload(self, topic: str, msg: dict):
        """
        處理模式 B 的 commanded payload。

        payload 結構：
        {
          "_meta": {..., "collection_mode": "commanded"},
          "production_context": {"lot_id": ..., "step_id": ..., ...},
          "data": {
            "trace_id": "...",
            "parameters": [
              {"svid": "SV001", "name": "Pressure", "values": [...], "unit": "Torr", "interval_ms": 1000},
              ...
            ],
            "start_time": "...",
            "end_time": "..."
          }
        }
        """
        meta = msg.get("_meta", {})
        ctx = msg.get("production_context", {})
        data = msg.get("data", {})

        equipment_path = meta.get("source", "")
        lot_id = ctx.get("lot_id")
        step_id = ctx.get("step_id")
        recipe_id = ctx.get("recipe_id")
        product_id = ctx.get("product_id")
        pass_number = ctx.get("pass_number", 1)

        # 1. 確保 production_run 存在（如果 EAP 是事後才上傳 trace data）
        run_id = self._ensure_production_run(
            lot_id=lot_id,
            equipment_path=equipment_path,
            step_id=step_id,
            pass_number=pass_number,
            recipe_id=recipe_id,
            product_id=product_id,
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            context=ctx,
        )

        # 2. 展開 trace data 的每個 parameter
        parameters = data.get("parameters", [])
        total_inserted = 0

        for param in parameters:
            svid = param.get("svid", "")
            name = param.get("name", svid)
            values = param.get("values", [])
            unit = param.get("unit")
            interval_ms = param.get("interval_ms", 1000)

            if not values:
                continue

            # 產生 tag（用 equipment_path + parameter name 作為 topic）
            sub_topic = f"{equipment_path}/Telemetry/{name}"
            parsed = {
                "asset_path": equipment_path,
                "category": "Telemetry",
                "data_point": name,
            }
            tag_id = self.tags.get_tag_id(sub_topic, parsed, unit=unit)

            # 產生時間序列（根據 start_time + interval_ms 推算每個取樣點的時間）
            trace_start = datetime.fromisoformat(
                data.get("start_time", meta.get("timestamp"))
            )

            # 批次 INSERT
            rows = []
            for i, value in enumerate(values):
                t = trace_start + timedelta(milliseconds=i * interval_ms)
                rows.append((t, tag_id, float(value), "good", run_id, lot_id, step_id))

            cur = self.db.cursor()
            execute_values(
                cur,
                """INSERT INTO ts_telemetry
                   (time, tag_id, value, quality, run_id, lot_id, step_id)
                   VALUES %s""",
                rows,
                page_size=500
            )
            self.db.commit()
            cur.close()

            total_inserted += len(rows)

        logger.info(
            f"Commanded trace: {lot_id} @ {equipment_path} "
            f"step={step_id} → {len(parameters)} params, "
            f"{total_inserted} 筆寫入"
        )

    def _ensure_production_run(self, **kwargs) -> int:
        """確保 production_run 紀錄存在，回傳 run_id"""
        cur = self.db.cursor()

        # 先查是否已存在
        cur.execute(
            """SELECT run_id FROM production_run
               WHERE lot_id = %s AND equipment_path = %s
                 AND step_id = %s AND pass_number = %s""",
            (kwargs["lot_id"], kwargs["equipment_path"],
             kwargs["step_id"], kwargs["pass_number"])
        )
        row = cur.fetchone()

        if row:
            cur.close()
            return row[0]

        # 建新的
        cur.execute(
            """INSERT INTO production_run
               (lot_id, equipment_path, start_time, end_time,
                step_id, pass_number, recipe_id, product_id,
                status, source, context)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'completed','eap',%s)
               RETURNING run_id""",
            (kwargs["lot_id"], kwargs["equipment_path"],
             kwargs.get("start_time"), kwargs.get("end_time"),
             kwargs["step_id"], kwargs["pass_number"],
             kwargs.get("recipe_id"), kwargs.get("product_id"),
             Json(kwargs.get("context")) if kwargs.get("context") else None)
        )
        run_id = cur.fetchone()[0]
        self.db.commit()
        cur.close()
        return run_id


# =============================================================================
# 3. Context Enricher（整合兩種模式）
# =============================================================================

class ContextEnricher:
    """
    Production Context Enrichment 的主入口。

    整合兩種模式：
      - Continuous：查 ProductionRunCache 補上 context
      - Commanded：TraceDataWriter 直接寫入

    也負責處理 MES 事件（LotMoveIn / LotMoveOut）。
    """

    def __init__(self, db_conn, tag_cache):
        self.db = db_conn
        self.run_cache = ProductionRunCache(db_conn)
        self.trace_writer = TraceDataWriter(db_conn, tag_cache)
        self.tags = tag_cache

    # ── MES 事件處理 ──────────────────────────────────────

    def handle_mes_event(self, event_code: str, event: dict):
        """
        處理 CDC 送來的 MES 事件。

        在 consumer_example.py 的 _write_event() 中，
        如果 event_code 是 LotMoveIn / LotMoveOut，呼叫此方法。
        """
        if event_code == "LotMoveIn":
            self.run_cache.on_lot_move_in(event)
        elif event_code == "LotMoveOut":
            self.run_cache.on_lot_move_out(event)

    # ── 模式 A：持續上傳 ─────────────────────────────────

    def get_active_run(self, equipment_path: str,
                       chamber_id: str = None) -> Optional[dict]:
        """
        查找設備目前的 active production run。
        傳回 None 表示設備 idle（telemetry 不帶 lot context）。
        """
        return self.run_cache.get_active_run(equipment_path, chamber_id)

    def enrich_telemetry_row(self, equipment_path: str) -> dict:
        """
        回傳要填入 ts_telemetry 的額外欄位。

        用法：
            extra = enricher.enrich_telemetry_row(equipment_path)
            INSERT INTO ts_telemetry (..., run_id, lot_id, step_id)
            VALUES (..., extra['run_id'], extra['lot_id'], extra['step_id'])
        """
        run = self.get_active_run(equipment_path)
        if run:
            return {
                "run_id": run["run_id"],
                "lot_id": run["lot_id"],
                "step_id": run["step_id"],
            }
        return {"run_id": None, "lot_id": None, "step_id": None}

    # ── 模式 B：指令式收集 ───────────────────────────────

    def write_commanded(self, topic: str, msg: dict):
        """
        處理 EAP 的 commanded trace data payload。
        """
        self.trace_writer.write_commanded_payload(topic, msg)

    # ── 統一入口 ─────────────────────────────────────────

    def process_message(self, topic: str, payload_bytes: bytes) -> Optional[dict]:
        """
        統一處理入口。辨識 collection_mode 後分流。

        回傳：
          - continuous 模式：回傳 enriched context dict（呼叫者自己寫 DB）
          - commanded 模式：直接寫 DB，回傳 None
        """
        try:
            msg = json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        meta = msg.get("_meta", {})
        mode = meta.get("collection_mode", "continuous")

        if mode == "commanded":
            self.write_commanded(topic, msg)
            return None  # 已經寫了，呼叫者不需要再寫
        else:
            # 回傳 context，讓呼叫者加到 INSERT 中
            equipment_path = meta.get("source", "")
            return {
                "msg": msg,
                "context": self.enrich_telemetry_row(equipment_path),
                "mode": "continuous",
            }
