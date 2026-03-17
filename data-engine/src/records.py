"""
Data Transfer Objects (DTOs) for the Data Engine Pipeline.
"""
from datetime import datetime
from typing import Optional


class TelemetryRecord:
    """ts_telemetry 寫入記錄。"""
    __slots__ = ("time", "tag_id", "value", "value_text", "value_json", "quality", "run_id", "lot_id", "context_data")
    def __init__(self, time: datetime, tag_id: int, value: Optional[float] = None, value_text: Optional[str] = None, value_json: object = None, quality: str = "good", run_id: Optional[int] = None, lot_id: Optional[str] = None, context_data: Optional[dict] = None):
        self.time = time
        self.tag_id = tag_id
        self.value = value
        self.value_text = value_text
        self.value_json = value_json
        self.quality = quality
        self.run_id = run_id
        self.lot_id = lot_id
        self.context_data = context_data

class RawPayloadRecord:
    """ts_raw_payloads 寫入記錄。"""
    __slots__ = ("time", "topic", "payload", "schema_id", "payload_size")
    def __init__(self, time: datetime, topic: str, payload: dict, schema_id: Optional[int] = None, payload_size: int = 0):
        self.time = time
        self.topic = topic
        self.payload = payload
        self.schema_id = schema_id
        self.payload_size = payload_size

class StatusRecord:
    """ts_status 寫入記錄。"""
    __slots__ = ("time", "tag_id", "state_code", "sub_state_code", "code_category", "mode", "run_id", "lot_id", "details", "context_data")
    def __init__(self, time: datetime, tag_id: int, state_code: str, sub_state_code: Optional[str] = None, code_category: Optional[str] = None, mode: Optional[str] = None, run_id: Optional[int] = None, lot_id: Optional[str] = None, details: Optional[object] = None, context_data: Optional[dict] = None):
        self.time = time
        self.tag_id = tag_id
        self.state_code = state_code
        self.sub_state_code = sub_state_code
        self.code_category = code_category
        self.mode = mode
        self.run_id = run_id
        self.lot_id = lot_id
        self.details = details
        self.context_data = context_data    

class AlarmRecord:
    """ts_alarms 寫入記錄。"""
    __slots__ = ("time", "tag_id", "alarm_id", "alarm_code", "sub_alarm_code", "code_category", "severity", "message", "alarm_status", "value", "threshold", "run_id", "lot_id", "details", "context_data")
    def __init__(self, time: datetime, tag_id: int, alarm_id: str, alarm_code: str, sub_alarm_code: Optional[str] = None, code_category: Optional[str] = None, severity: str = "warning", message: Optional[str] = None, alarm_status: str = "active", value: Optional[float] = None, threshold: Optional[float] = None, run_id: Optional[int] = None, lot_id: Optional[str] = None, details: Optional[object] = None, context_data: Optional[dict] = None):
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
        self.context_data = context_data

class EventRecord:
    """ts_events 寫入記錄。"""
    __slots__ = ("time", "tag_id", "event_id", "event_code", "sub_event_code", "code_category", "result", "run_id", "lot_id", "details", "context_data")
    def __init__(self, time: datetime, tag_id: int, event_id: str, event_code: str, sub_event_code: Optional[str] = None, code_category: Optional[str] = None, result: Optional[str] = None, run_id: Optional[int] = None, lot_id: Optional[str] = None, details: Optional[object] = None, context_data: Optional[dict] = None):
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
        self.context_data = context_data

class MeasurementRecord:
    """ts_measurements 寫入記錄。"""
    __slots__ = ("time", "tag_id", "value", "spec_upper", "spec_lower", "target_value", "result", "run_id", "lot_id", "step_id", "sample_id", "sample_position", "inspector", "context", "details", "context_data")
    def __init__(self, time: datetime, tag_id: int, value: float, spec_upper: Optional[float] = None, spec_lower: Optional[float] = None, target_value: Optional[float] = None, result: str = "pass", run_id: Optional[int] = None, lot_id: Optional[str] = None, step_id: Optional[str] = None, sample_id: Optional[str] = None, sample_position: Optional[str] = None, inspector: Optional[str] = None, context: Optional[dict] = None, details: Optional[object] = None, context_data: Optional[dict] = None):
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
        self.context_data = context_data

class MetricsRecord:
    """ts_metrics 寫入記錄。"""
    __slots__ = ("time", "tag_id", "metric_category", "metric_code", "sub_metric_code", "period", "values", "run_id", "lot_id", "context", "details", "context_data")
    def __init__(self, time: datetime, tag_id: int, metric_category: str, metric_code: str, sub_metric_code: Optional[str] = None, period: Optional[str] = None, values: dict = None, run_id: Optional[int] = None, lot_id: Optional[str] = None, context: Optional[dict] = None, details: Optional[object] = None, context_data: Optional[dict] = None):
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
        self.context_data = context_data
