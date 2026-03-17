"""
UNS Data Engine — DB Writer

Batch INSERT to ts_telemetry + ts_raw_payloads (Dual Storage)。
使用 psycopg2.extras.execute_values 做高效批次寫入。
支援 buffer + flush 機制、冪等寫入 (ON CONFLICT DO NOTHING)。
"""
import logging
import threading
import time

from psycopg2.extras import Json, execute_values

from .asdict_helper import _asdict_minus_context_data
from .db_pool import DBPool
from .display_value_generator import _generate_display_value
from .records import (
    AlarmRecord,
    EventRecord,
    MeasurementRecord,
    MetricsRecord,
    RawPayloadRecord,
    StatusRecord,
    TelemetryRecord,
)

logger = logging.getLogger("uns.db_writer")

class DBWriter:
    """
    批次 DB 寫入器。

    累積 records 到 buffer → 達到 BATCH_SIZE 或 BATCH_INTERVAL_SEC 後 flush。
    ts_telemetry 用 ON CONFLICT DO NOTHING 確保冪等。
    """

    def __init__(
        self,
        db_pool: DBPool,
        batch_size: int = 100,
        batch_interval_sec: float = 1.0,
    ):
        self._db_pool = db_pool
        self._batch_size = batch_size
        self._batch_interval = batch_interval_sec

        self._telemetry_buffer: list[TelemetryRecord] = []
        self._status_buffer: list[StatusRecord] = []
        self._alarm_buffer: list[AlarmRecord] = []
        self._event_buffer: list[EventRecord] = []
        self._metric_buffer: list[MetricsRecord] = []
        self._meas_buffer: list[MeasurementRecord] = []
        self._raw_buffer: list[RawPayloadRecord] = []
        
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()

        # 活躍 Tag 追蹤 (用於批次更新 last_data_at)
        self._seen_tags: set[int] = set()
        
        # Latest Values 快照快取 (用於批次 UPSERT 到 latest_values)
        self._latest_values_to_upsert: dict[int, dict] = {}

        # 統計
        self._total_telemetry_written = 0
        self._total_raw_written = 0
        self._total_errors = 0

    def _mark_tag_seen(self, tag_id: int):
        """記錄活躍的 Tag ID。"""
        if tag_id:
            self._seen_tags.add(tag_id)

    def _update_latest_cache(self, tag_id: int, category: str, record: object):
        """更新最新值快照緩存，確保同一批次中只保留每個 Tag 最新的記錄。"""
        if not tag_id or not hasattr(record, "time"):
            return

        time_val = record.time
        existing = self._latest_values_to_upsert.get(tag_id)
        if not existing or time_val >= existing["time"]:
            self._latest_values_to_upsert[tag_id] = {
                "tag_id": tag_id,
                "time": time_val,
                "category": category,
                "display_value": _generate_display_value(category, record),
                "data": _asdict_minus_context_data(record),
                "quality": getattr(record, "quality", "good"),
                "run_id": getattr(record, "run_id", None),
                "context_data": getattr(record, "context_data", None),
            }

    def add_telemetry(self, record: TelemetryRecord):
        """新增一筆 telemetry 記錄到 buffer。"""
        with self._lock:
            self._mark_tag_seen(record.tag_id)
            self._update_latest_cache(record.tag_id, "telemetry", record)
            self._telemetry_buffer.append(record)
            if len(self._telemetry_buffer) >= self._batch_size:
                self._flush_telemetry()

    def add_status(self, record: StatusRecord):
        """新增一筆 status 記錄到 buffer。"""
        with self._lock:
            self._mark_tag_seen(record.tag_id)
            self._update_latest_cache(record.tag_id, "status", record)
            self._status_buffer.append(record)
            if len(self._status_buffer) >= self._batch_size:
                self._flush_status()

    def add_alarm(self, record: AlarmRecord):
        """新增一筆 alarm 記錄到 buffer。"""
        with self._lock:
            self._mark_tag_seen(record.tag_id)
            self._update_latest_cache(record.tag_id, "alarm", record)
            self._alarm_buffer.append(record)
            if len(self._alarm_buffer) >= self._batch_size:
                self._flush_alarm()

    def add_event(self, record: EventRecord):
        """新增一筆 event 記錄到 buffer。"""
        with self._lock:
            self._mark_tag_seen(record.tag_id)
            self._update_latest_cache(record.tag_id, "event", record)
            self._event_buffer.append(record)
            if len(self._event_buffer) >= self._batch_size:
                self._flush_event()

    def add_metrics(self, record: MetricsRecord):
        """新增一筆 metrics 記錄到 buffer。"""
        with self._lock:
            self._mark_tag_seen(record.tag_id)
            self._update_latest_cache(record.tag_id, "metrics", record)
            self._metric_buffer.append(record)
            if len(self._metric_buffer) >= self._batch_size:
                self._flush_metrics()

    def add_measurement(self, record: MeasurementRecord):
        """新增一筆 measurement 記錄到 buffer。"""
        with self._lock:
            self._mark_tag_seen(record.tag_id)
            self._update_latest_cache(record.tag_id, "measurement", record)
            self._meas_buffer.append(record)
            if len(self._meas_buffer) >= self._batch_size:
                self._flush_measurement()

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
            self._flush_status()
            self._flush_alarm()
            self._flush_event()
            self._flush_metrics()
            self._flush_measurement()
            self._flush_raw()
            self._flush_latest_values()
            self._flush_last_data_at()
            self._last_flush = time.monotonic()

    def _flush_latest_values(self):
        """批次 UPSERT 最新值到 latest_values 表。"""
        if not self._latest_values_to_upsert:
            return

        records = list(self._latest_values_to_upsert.values())
        self._latest_values_to_upsert.clear()

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO latest_values 
                       (tag_id, time, category, display_value, data, quality, run_id, context_data)
                       VALUES %s
                       ON CONFLICT (tag_id) DO UPDATE SET
                           time = EXCLUDED.time,
                           category = EXCLUDED.category,
                           display_value = EXCLUDED.display_value,
                           data = EXCLUDED.data,
                           quality = EXCLUDED.quality,
                           run_id = EXCLUDED.run_id,
                           context_data = EXCLUDED.context_data
                       WHERE EXCLUDED.time >= latest_values.time""",
                    [
                        (
                            r["tag_id"], r["time"], r["category"], r["display_value"],
                            Json(r["data"]), r["quality"], r["run_id"],
                            Json(r["context_data"]) if r["context_data"] is not None else None
                        )
                        for r in records
                    ],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                logger.debug("Flushed %d records to latest_values", len(records))
        except Exception as e:
            logger.error("Latest values flush failed: %s", e)
            self._total_errors += 1

    def _flush_last_data_at(self):
        """批次更新活躍 Tag 的最後見到時間。"""
        if not self._seen_tags:
            return

        tag_ids = list(self._seen_tags)
        self._seen_tags = set()

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                # 採用 IN 子句做批次更新，效率極高
                cur.execute(
                    "UPDATE tags SET last_data_at = NOW() WHERE tag_id IN %s",
                    (tuple(tag_ids),)
                )
                conn.commit()
                cur.close()
                logger.debug("Updated last_data_at for %d tags", len(tag_ids))
        except Exception as e:
            logger.error("Failed to update tags last_data_at: %s", e)
            self._total_errors += 1

    def _flush_telemetry(self):
        """批次寫入 ts_telemetry。"""
        if not self._telemetry_buffer:
            return
        records = self._telemetry_buffer
        self._telemetry_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_telemetry (time, tag_id, value, quality, run_id, lot_id)
                       VALUES %s ON CONFLICT DO NOTHING""",
                    [(r.time, r.tag_id, r.value, r.quality, r.run_id, r.lot_id) for r in records if r.value is not None],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
        except Exception as e:
            logger.error("Telemetry flush failed: %s", e)
            self._total_errors += 1

    def _flush_status(self):
        """批次寫入 ts_status。"""
        if not self._status_buffer:
            return
        records = self._status_buffer
        self._status_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_status (time, tag_id, state_code, sub_state_code, code_category, mode, run_id, lot_id, details)
                       VALUES %s ON CONFLICT DO NOTHING""",
                    [(r.time, r.tag_id, r.state_code, r.sub_state_code, r.code_category, r.mode, r.run_id, r.lot_id, Json(r.details) if r.details else None) for r in records],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
        except Exception as e:
            logger.error("Status flush failed: %s", e)
            self._total_errors += 1

    def _flush_alarm(self):
        """批次寫入 ts_alarms。"""
        if not self._alarm_buffer:
            return
        records = self._alarm_buffer
        self._alarm_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_alarms (time, tag_id, alarm_id, alarm_code, sub_alarm_code, code_category, severity, message, alarm_status, value, threshold, run_id, lot_id, details)
                       VALUES %s ON CONFLICT DO NOTHING""",
                    [(r.time, r.tag_id, r.alarm_id, r.alarm_code, r.sub_alarm_code, r.code_category, r.severity, r.message, r.alarm_status, r.value, r.threshold, r.run_id, r.lot_id, Json(r.details) if r.details else None) for r in records],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
        except Exception as e:
            logger.error("Alarm flush failed: %s", e)
            self._total_errors += 1

    def _flush_event(self):
        """批次寫入 ts_events。"""
        if not self._event_buffer:
            return
        records = self._event_buffer
        self._event_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_events (time, tag_id, event_id, event_code, sub_event_code, code_category, result, run_id, lot_id, details)
                       VALUES %s ON CONFLICT DO NOTHING""",
                    [(r.time, r.tag_id, r.event_id, r.event_code, r.sub_event_code, r.code_category, r.result, r.run_id, r.lot_id, Json(r.details) if r.details else None) for r in records],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
        except Exception as e:
            logger.error("Event flush failed: %s", e)
            self._total_errors += 1

    def _flush_metrics(self):
        """批次寫入 ts_metrics。"""
        if not self._metric_buffer:
            return
        records = self._metric_buffer
        self._metric_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_metrics (time, tag_id, metric_category, metric_code, sub_metric_code, period, values, run_id, lot_id, context, details)
                       VALUES %s ON CONFLICT DO NOTHING""",
                    [(r.time, r.tag_id, r.metric_category, r.metric_code, r.sub_metric_code, r.period, Json(r.values), r.run_id, r.lot_id, Json(r.context) if r.context else None, Json(r.details) if r.details else None) for r in records],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
        except Exception as e:
            logger.error("Metrics flush failed: %s", e)
            self._total_errors += 1

    def _flush_measurement(self):
        """批次寫入 ts_measurements。"""
        if not self._meas_buffer:
            return
        records = self._meas_buffer
        self._meas_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_measurements (time, tag_id, value, spec_upper, spec_lower, target_value, result, run_id, lot_id, step_id, sample_id, sample_position, inspector, context, details)
                       VALUES %s ON CONFLICT DO NOTHING""",
                    [(r.time, r.tag_id, r.value, r.spec_upper, r.spec_lower, r.target_value, r.result, r.run_id, r.lot_id, r.step_id, r.sample_id, r.sample_position, r.inspector, Json(r.context) if r.context else None, Json(r.details) if r.details else None) for r in records],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
        except Exception as e:
            logger.error("Measurement flush failed: %s", e)
            self._total_errors += 1

    def _flush_raw(self):
        """批次寫入 ts_raw_payloads。"""
        if not self._raw_buffer:
            return
        records = self._raw_buffer
        self._raw_buffer = []
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                execute_values(
                    cur,
                    """INSERT INTO ts_raw_payloads (time, mqtt_topic, payload, schema_id, payload_size)
                       VALUES %s""",
                    [(r.time, r.topic, Json(r.payload), r.schema_id, r.payload_size) for r in records],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_raw_written += len(records)
        except Exception as e:
            logger.error("Raw payload flush failed: %s", e)
            self._total_errors += 1

    @property
    def stats(self) -> dict:
        """回傳寫入統計。"""
        with self._lock:
            return {
                "telemetry_written": self._total_telemetry_written,
                "raw_written": self._total_raw_written,
                "errors": self._total_errors,
                "telemetry_buffer": len(self._telemetry_buffer),
                "status_buffer": len(self._status_buffer),
                "alarm_buffer": len(self._alarm_buffer),
                "event_buffer": len(self._event_buffer),
                "metric_buffer": len(self._metric_buffer),
                "meas_buffer": len(self._meas_buffer),
                "raw_buffer": len(self._raw_buffer),
            }

    def close(self):
        """Graceful shutdown：flush 剩餘 buffer。"""
        logger.info("DBWriter closing, flushing remaining buffer...")
        self.flush()
        logger.info("DBWriter stats: %s", self.stats)
