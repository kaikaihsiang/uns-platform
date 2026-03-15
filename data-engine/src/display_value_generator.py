from .records import (
    AlarmRecord,
    EventRecord,
    MeasurementRecord,
    MetricsRecord,
    StatusRecord,
    TelemetryRecord,
)


def _generate_display_value(category: str, record: object) -> str:
    """根據 Category 產生易讀的顯示字串。"""
    try:
        if category == "telemetry" and isinstance(record, TelemetryRecord):
            unit = getattr(record, 'unit', '') or ''
            val = getattr(record, 'value', None)
            if val is not None and isinstance(val, (int, float)):
                return f"{val:.2f} {unit}".strip()
            if getattr(record, 'value_text', None):
                return record.value_text
            if getattr(record, 'value_json', None):
                import json
                return json.dumps(record.value_json)
            return "0.00"
        
        if category == "status" and isinstance(record, StatusRecord):
            parts = [record.state_code, record.sub_state_code, record.mode]
            main_part = f"({parts[1]})" if parts[1] else ""
            mode_part = f"- {parts[2]}" if parts[2] else ""
            return f"{parts[0]} {main_part} {mode_part}".replace("  ", " ").strip()
        
        if category == "alarm" and isinstance(record, AlarmRecord):
            return f"{record.alarm_status.capitalize()} - {record.severity.capitalize()} ({record.alarm_code})"
        
        if category == "event" and isinstance(record, EventRecord):
            result_part = f" ({record.result})" if record.result else ""
            return f"{record.event_code}{result_part}"
        
        if category == "metrics" and isinstance(record, MetricsRecord):
            if record.metric_code == "OEE" and isinstance(record.values, dict):
                parts = [f"{k.upper()}:{v}" for k, v in record.values.items()]
                return f"OEE ({', '.join(parts)})"
            return record.metric_code
        
        if category == "measurement" and isinstance(record, MeasurementRecord):
            unit = getattr(record, 'unit', '') or ''
            val = getattr(record, 'value', None)
            result_part = f" ({record.result.capitalize()})" if record.result else ""
            if val is not None and isinstance(val, (int, float)):
                return f"{val:.2f} {unit}{result_part}".strip()
            return f"{val} {unit}{result_part}".strip()
    except Exception:
        # Fallback to a safe string
        return str(getattr(record, 'tag_id', 'Unknown'))
    return ""
