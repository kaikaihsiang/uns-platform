"""
UNS Data Engine — DB Writer

Batch INSERT to ts_telemetry + ts_raw_payloads (Dual Storage)。
使用 psycopg2.extras.execute_values 做高效批次寫入。
支援 buffer + flush 機制、冪等寫入 (ON CONFLICT DO NOTHING)。
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values, Json

logger = logging.getLogger("uns.db_writer")


class TelemetryRecord:
    """ts_telemetry 寫入記錄。"""

    __slots__ = ("time", "tag_id", "value", "value_text", "value_json", "quality")

    def __init__(
        self,
        time: datetime,
        tag_id: int,
        value: Optional[float] = None,
        value_text: Optional[str] = None,
        value_json: object = None,
        quality: str = "good",
    ):
        self.time = time
        self.tag_id = tag_id
        self.value = value
        self.value_text = value_text
        self.value_json = value_json
        self.quality = quality


class RawPayloadRecord:
    """ts_raw_payloads 寫入記錄。"""

    __slots__ = ("time", "topic", "payload", "schema_type_id", "payload_size")

    def __init__(
        self,
        time: datetime,
        topic: str,
        payload: dict,
        schema_type_id: Optional[int] = None,
        payload_size: int = 0,
    ):
        self.time = time
        self.topic = topic
        self.payload = payload
        self.schema_type_id = schema_type_id
        self.payload_size = payload_size


class DBWriter:
    """
    批次 DB 寫入器。

    累積 records 到 buffer → 達到 BATCH_SIZE 或 BATCH_INTERVAL_SEC 後 flush。
    ts_telemetry 用 ON CONFLICT DO NOTHING 確保冪等。
    """

    def __init__(
        self,
        db_conn,
        batch_size: int = 100,
        batch_interval_sec: float = 1.0,
    ):
        self._db = db_conn
        self._batch_size = batch_size
        self._batch_interval = batch_interval_sec

        self._telemetry_buffer: list[TelemetryRecord] = []
        self._raw_buffer: list[RawPayloadRecord] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()

        # 統計
        self._total_telemetry_written = 0
        self._total_raw_written = 0
        self._total_errors = 0

    def add_telemetry(self, record: TelemetryRecord):
        """新增一筆 telemetry 記錄到 buffer。"""
        with self._lock:
            self._telemetry_buffer.append(record)
            if len(self._telemetry_buffer) >= self._batch_size:
                self._flush_telemetry()

    def add_raw_payload(self, record: RawPayloadRecord):
        """新增一筆 raw payload 記錄到 buffer。"""
        with self._lock:
            self._raw_buffer.append(record)
            if len(self._raw_buffer) >= self._batch_size:
                self._flush_raw()

    def tick(self):
        """
        定期呼叫，檢查是否需要 time-based flush。
        應由外部 event loop 定期呼叫（如每 0.5 秒）。
        """
        now = time.monotonic()
        if now - self._last_flush >= self._batch_interval:
            self.flush()

    def flush(self):
        """強制 flush 所有 buffer。"""
        with self._lock:
            self._flush_telemetry()
            self._flush_raw()
            self._last_flush = time.monotonic()

    def _flush_telemetry(self):
        """批次寫入 ts_telemetry。"""
        if not self._telemetry_buffer:
            return

        records = self._telemetry_buffer
        self._telemetry_buffer = []

        try:
            cur = self._db.cursor()
            # 使用 execute_values 做批次 INSERT
            # ON CONFLICT 確保冪等（retained message 重啟時不重複寫）
            execute_values(
                cur,
                """INSERT INTO ts_telemetry (time, tag_id, value, quality)
                   VALUES %s
                   ON CONFLICT DO NOTHING""",
                [
                    (r.time, r.tag_id, r.value, r.quality)
                    for r in records
                    if r.value is not None
                ],
                page_size=500,
            )

            # value_text 的記錄另外處理（不同欄位）
            text_records = [r for r in records if r.value_text is not None]
            if text_records:
                # 目前 ts_telemetry 只有 value (DOUBLE PRECISION)
                # value_text 寫入需要擴展 ts_telemetry 表
                # Phase 1 先把 string 型別跳過或 cast
                logger.debug("Skipping %d text records (Phase 1)", len(text_records))

            self._db.commit()
            cur.close()
            self._total_telemetry_written += len(records)
            logger.debug("Flushed %d telemetry records", len(records))

        except psycopg2.Error as e:
            logger.error("Telemetry flush failed: %s", e)
            self._total_errors += 1
            try:
                self._db.rollback()
            except Exception:
                pass

    def _flush_raw(self):
        """批次寫入 ts_raw_payloads。"""
        if not self._raw_buffer:
            return

        records = self._raw_buffer
        self._raw_buffer = []

        try:
            cur = self._db.cursor()
            execute_values(
                cur,
                """INSERT INTO ts_raw_payloads
                   (time, mqtt_topic, payload, schema_type_id, payload_size)
                   VALUES %s""",
                [
                    (r.time, r.topic, Json(r.payload), r.schema_type_id, r.payload_size)
                    for r in records
                ],
                page_size=500,
            )
            self._db.commit()
            cur.close()
            self._total_raw_written += len(records)
            logger.debug("Flushed %d raw payload records", len(records))

        except psycopg2.Error as e:
            logger.error("Raw payload flush failed: %s", e)
            self._total_errors += 1
            try:
                self._db.rollback()
            except Exception:
                pass

    @property
    def stats(self) -> dict:
        """回傳寫入統計。"""
        return {
            "telemetry_written": self._total_telemetry_written,
            "raw_written": self._total_raw_written,
            "errors": self._total_errors,
            "telemetry_buffer": len(self._telemetry_buffer),
            "raw_buffer": len(self._raw_buffer),
        }

    def close(self):
        """Graceful shutdown：flush 剩餘 buffer。"""
        logger.info("DBWriter closing, flushing remaining buffer...")
        self.flush()
        logger.info("DBWriter stats: %s", self.stats)
