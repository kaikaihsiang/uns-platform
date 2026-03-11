"""
UNS Data Engine — DB Writer

Batch INSERT to ts_telemetry + ts_raw_payloads (Dual Storage)。
使用 psycopg2.extras.execute_values 做高效批次寫入。
支援 buffer + flush 機制、冪等寫入 (ON CONFLICT DO NOTHING)。
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

from psycopg2.extras import Json, execute_values

from .db_pool import DBPool

logger = logging.getLogger("uns.db_writer")


class TelemetryRecord:
    """ts_telemetry 寫入記錄。"""

    __slots__ = ("time", "tag_id", "value", "value_text", "value_json", "quality", "run_id", "lot_id")

    def __init__(
        self,
        time: datetime,
        tag_id: int,
        value: Optional[float] = None,
        value_text: Optional[str] = None,
        value_json: object = None,
        quality: str = "good",
        run_id: Optional[int] = None,
        lot_id: Optional[str] = None,
    ):
        self.time = time
        self.tag_id = tag_id
        self.value = value
        self.value_text = value_text
        self.value_json = value_json
        self.quality = quality
        self.run_id = run_id
        self.lot_id = lot_id


class RawPayloadRecord:
    """ts_raw_payloads 寫入記錄。"""

    __slots__ = ("time", "topic", "payload", "schema_id", "payload_size")

    def __init__(
        self,
        time: datetime,
        topic: str,
        payload: dict,
        schema_id: Optional[int] = None,
        payload_size: int = 0,
    ):
        self.time = time
        self.topic = topic
        self.payload = payload
        self.schema_id = schema_id
        self.payload_size = payload_size


class StatusRecord:
    """ts_status 寫入記錄。"""
    __slots__ = ("time", "tag_id", "state_code", "sub_state_code", "code_category", "mode", "run_id", "lot_id", "details")

    def __init__(self, time: datetime, tag_id: int, state_code: str, 
                 sub_state_code: Optional[str] = None, code_category: Optional[str] = None,
                 mode: Optional[str] = None,
                 run_id: Optional[int] = None, lot_id: Optional[str] = None,
                 details: Optional[object] = None):
        self.time = time
        self.tag_id = tag_id
        self.state_code = state_code
        self.sub_state_code = sub_state_code
        self.code_category = code_category
        self.mode = mode
        self.run_id = run_id
        self.lot_id = lot_id
        self.details = details


class AlarmRecord:
    """ts_alarms 寫入記錄。"""
    __slots__ = ("time", "tag_id", "alarm_id", "alarm_code", "sub_alarm_code", "code_category", "severity", "message", "alarm_status", "value", "threshold", "run_id", "lot_id", "details")

    def __init__(self, time: datetime, tag_id: int, alarm_id: str, alarm_code: str, 
                 sub_alarm_code: Optional[str] = None, code_category: Optional[str] = None,
                 severity: str = "warning", message: Optional[str] = None, alarm_status: str = "active",
                 value: Optional[float] = None, threshold: Optional[float] = None,
                 run_id: Optional[int] = None, lot_id: Optional[str] = None,
                 details: Optional[object] = None):
        self.time = time
        self.tag_id = tag_id
        self.alarm_id = alarm_id
        self.alarm_code = alarm_code
        self.sub_alarm_code = sub_alarm_code
        self.code_category = code_category
        self.severity = severity
        self.message = message
        self.alarm_status = alarm_status
        self.value = value
        self.threshold = threshold
        self.run_id = run_id
        self.lot_id = lot_id
        self.details = details


class EventRecord:
    """ts_events 寫入記錄。"""
    __slots__ = ("time", "tag_id", "event_id", "event_code", "sub_event_code", "code_category", "result", "run_id", "lot_id", "details")

    def __init__(self, time: datetime, tag_id: int, event_id: str, event_code: str,
                 sub_event_code: Optional[str] = None, code_category: Optional[str] = None,
                 result: Optional[str] = None,
                 run_id: Optional[int] = None, lot_id: Optional[str] = None,
                 details: Optional[object] = None):
        self.time = time
        self.tag_id = tag_id
        self.event_id = event_id
        self.event_code = event_code
        self.sub_event_code = sub_event_code
        self.code_category = code_category
        self.result = result
        self.run_id = run_id
        self.lot_id = lot_id
        self.details = details


class MeasurementRecord:
    """ts_measurements 寫入記錄。"""
    __slots__ = ("time", "tag_id", "value", "spec_upper", "spec_lower", "target_value", "result", "run_id", "lot_id", "step_id", "sample_id", "sample_position", "inspector", "context", "details")

    def __init__(self, time: datetime, tag_id: int, value: float,
                 spec_upper: Optional[float] = None, spec_lower: Optional[float] = None,
                 target_value: Optional[float] = None,
                 result: str = "pass",
                 run_id: Optional[int] = None, lot_id: Optional[str] = None,
                 step_id: Optional[str] = None,
                 sample_id: Optional[str] = None, sample_position: Optional[str] = None,
                 inspector: Optional[str] = None,
                 context: Optional[dict] = None,
                 details: Optional[object] = None):
        self.time = time
        self.tag_id = tag_id
        self.value = value
        self.spec_upper = spec_upper
        self.spec_lower = spec_lower
        self.target_value = target_value
        self.result = result
        self.run_id = run_id
        self.lot_id = lot_id
        self.step_id = step_id
        self.sample_id = sample_id
        self.sample_position = sample_position
        self.inspector = inspector
        self.context = context
        self.details = details


class MetricsRecord:
    """ts_metrics 寫入記錄。"""
    __slots__ = ("time", "tag_id", "metric_category", "metric_code", "sub_metric_code", "period", "values", "run_id", "lot_id", "context", "details")

    def __init__(self, time: datetime, tag_id: int, 
                 metric_category: str, metric_code: str, sub_metric_code: Optional[str] = None,
                 period: Optional[str] = None,
                 values: dict = None,
                 run_id: Optional[int] = None, lot_id: Optional[str] = None,
                 context: Optional[dict] = None,
                 details: Optional[object] = None):
        self.time = time
        self.tag_id = tag_id
        self.metric_category = metric_category
        self.metric_code = metric_code
        self.sub_metric_code = sub_metric_code
        self.period = period
        self.values = values or {}
        self.run_id = run_id
        self.lot_id = lot_id
        self.context = context
        self.details = details


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

    def add_status(self, record: StatusRecord):
        """新增一筆 status 記錄到 buffer。"""
        with self._lock:
            self._status_buffer.append(record)
            if len(self._status_buffer) >= self._batch_size:
                self._flush_status()

    def add_alarm(self, record: AlarmRecord):
        """新增一筆 alarm 記錄到 buffer。"""
        with self._lock:
            self._alarm_buffer.append(record)
            if len(self._alarm_buffer) >= self._batch_size:
                self._flush_alarm()

    def add_event(self, record: EventRecord):
        """新增一筆 event 記錄到 buffer。"""
        with self._lock:
            self._event_buffer.append(record)
            if len(self._event_buffer) >= self._batch_size:
                self._flush_event()

    def add_metrics(self, record: MetricsRecord):
        """新增一筆 metrics 記錄到 buffer。"""
        with self._lock:
            self._metric_buffer.append(record)
            if len(self._metric_buffer) >= self._batch_size:
                self._flush_metrics()

    def add_measurement(self, record: MeasurementRecord):
        """新增一筆 measurement 記錄到 buffer。"""
        with self._lock:
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
            self._last_flush = time.monotonic()

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
                       VALUES %s
                       ON CONFLICT DO NOTHING""",
                    [
                        (r.time, r.tag_id, r.value, r.quality, r.run_id, r.lot_id)
                        for r in records
                        if r.value is not None
                    ],
                    page_size=500,
                )

                text_records = [r for r in records if r.value_text is not None]
                if text_records:
                    logger.debug("Skipping %d text records (Phase 1)", len(text_records))

                conn.commit()
                cur.close()
                self._total_telemetry_written += len(records)
                logger.info("Flushed %d telemetry records to ts_telemetry", len(records))

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
                    """INSERT INTO ts_raw_payloads
                       (time, mqtt_topic, payload, schema_id, payload_size)
                       VALUES %s""",
                    [
                        (r.time, r.topic, Json(r.payload), r.schema_id, r.payload_size)
                        for r in records
                    ],
                    page_size=500,
                )
                conn.commit()
                cur.close()
                self._total_raw_written += len(records)
                logger.debug("Flushed %d raw payload records", len(records))

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
                "meas_buffer": len(self._meas_buffer),
                "raw_buffer": len(self._raw_buffer),
            }

    def close(self):
        """Graceful shutdown：flush 剩餘 buffer。"""
        logger.info("DBWriter closing, flushing remaining buffer...")
        self.flush()
        logger.info("DBWriter stats: %s", self.stats)
