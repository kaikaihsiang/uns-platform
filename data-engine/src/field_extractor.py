"""
UNS Data Engine — Field Extractor

依 Schema Type fields 定義，使用 jsonpath-ng 從 payload 取值。
每個 field → (tag_id, value, timestamp)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from jsonpath_ng import parse as jsonpath_parse

from .schema_matcher import FieldDef, SchemaMatch

logger = logging.getLogger("uns.field_extractor")


class ExtractedValue:
    """單一欄位的取值結果。"""

    __slots__ = (
        "field_name", "tag_suffix", "value", "value_text", "value_json",
        "field_type", "unit", "deadband", "timestamp", "persist", "target_column",
        "is_schema_defined"
    )

    def __init__(
        self,
        field_name: str,
        tag_suffix: str,
        value: Optional[float] = None,
        value_text: Optional[str] = None,
        value_json: object = None,
        field_type: str = "float",
        unit: Optional[str] = None,
        deadband: object = None,
        timestamp: Optional[datetime] = None,
        persist: bool = True,
        target_column: Optional[str] = None,
        is_schema_defined: bool = True
    ):
        self.field_name = field_name
        self.tag_suffix = tag_suffix
        self.value = value
        self.value_text = value_text
        self.value_json = value_json
        self.field_type = field_type
        self.unit = unit
        self.deadband = deadband
        self.timestamp = timestamp
        self.persist = persist
        self.target_column = target_column
        self.is_schema_defined = is_schema_defined


# jsonpath expression 快取（避免重複 parse）
_jsonpath_cache: dict[str, object] = {}


def _get_jsonpath(path: str):
    """取得或建立 JSONPath expression。"""
    if path not in _jsonpath_cache:
        _jsonpath_cache[path] = jsonpath_parse(path)
    return _jsonpath_cache[path]


def _extract_timestamp(
    payload: dict,
    timestamp_field: Optional[str],
    receive_time: datetime,
) -> datetime:
    """
    從 payload 取得 timestamp。
    優先用 payload 中的欄位，fallback 到 receive time。
    """
    if timestamp_field:
        expr = _get_jsonpath(timestamp_field)
        matches = expr.find(payload)
        if matches:
            raw_ts = matches[0].value
            try:
                if isinstance(raw_ts, (int, float)):
                    if raw_ts > 1e12:
                        raw_ts = raw_ts / 1000.0
                    return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                elif isinstance(raw_ts, str):
                    for fmt in (
                        "%Y-%m-%dT%H:%M:%S.%f%z",
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S",
                    ):
                        try:
                            ts = datetime.strptime(raw_ts, fmt)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            return ts
                        except ValueError:
                            continue
                    logger.warning("Cannot parse timestamp string: %s", raw_ts)
            except Exception as e:
                logger.warning("Timestamp extraction failed: %s", e)

    return receive_time


def _coerce_value(raw_value, field_type: str) -> tuple:
    """依 field_type 強制轉型。"""
    if field_type in ("float", "integer"):
        try:
            return (float(raw_value), None, None)
        except (TypeError, ValueError):
            return (None, str(raw_value), None)
    elif field_type == "string":
        return (None, str(raw_value), None)
    elif field_type == "boolean":
        if isinstance(raw_value, bool):
            return (1.0 if raw_value else 0.0, None, None)
        try:
            return (float(raw_value), None, None)
        except (TypeError, ValueError):
            return (1.0 if raw_value else 0.0, None, None)
    elif field_type == "json":
        return (None, None, raw_value)
    else:
        try:
            return (float(raw_value), None, None)
        except (TypeError, ValueError):
            return (None, str(raw_value), None)


def _detect_type(val) -> str:
    """從原始值推斷資料型別。"""
    if isinstance(val, bool): return "boolean"
    if isinstance(val, (int, float)): return "float"
    if isinstance(val, (dict, list)): return "json"
    return "string"


class FieldExtractor:
    def extract(
        self,
        payload: dict,
        schema: SchemaMatch,
        receive_time: Optional[datetime] = None,
    ) -> list[ExtractedValue]:
        """
        從 payload 根據 schema.fields 定義取值。
        同時捕捉真正未定義在 Schema 裡的「遺漏」欄位。
        """
        if receive_time is None:
            receive_time = datetime.now(timezone.utc)

        timestamp = _extract_timestamp(payload, schema.timestamp_field, receive_time)
        results = []
        
        # 追蹤已處理的 Payload Data 鍵，防止重複捕捉
        processed_top_keys = set()

        # 1. 處理定義好的欄位 (Schema-driven)
        for field_def in schema.fields:
            if not field_def.extract:
                continue

            extracted = self._extract_field(payload, field_def, timestamp)
            if extracted:
                for ev in extracted:
                    ev.is_schema_defined = True
                    results.append(ev)
                
                # 簡單推斷這個欄位來自哪個 top-level data key
                path = field_def.path or f"$.{field_def.name}"
                if path.startswith("$.data."):
                    top_key = path.split(".")[2].split("[")[0]
                    processed_top_keys.add(top_key)

        # 2. 捕捉遺珠 (Truly Unknown Fields)
        data_block = payload.get("data", {})
        if isinstance(data_block, dict):
            for key, val in data_block.items():
                if key not in processed_top_keys:
                    dtype = _detect_type(val)
                    val_f, val_t, val_j = _coerce_value(val, dtype)
                    results.append(ExtractedValue(
                        field_name=key,
                        tag_suffix=key,
                        value=val_f,
                        value_text=val_t,
                        value_json=val_j,
                        field_type=dtype,
                        timestamp=timestamp,
                        persist=True,
                        target_column=None,
                        is_schema_defined=False
                    ))

        return results

    def extract_flat(self, payload: dict, receive_time: Optional[datetime] = None) -> list[ExtractedValue]:
        if receive_time is None:
            receive_time = datetime.now(timezone.utc)
        results = []
        for key, raw_value in payload.items():
            if key.startswith("_"): continue
            val_f, val_t, val_j = _coerce_value(raw_value, "float")
            results.append(ExtractedValue(
                field_name=key, tag_suffix=key,
                value=val_f, value_text=val_t, value_json=val_j,
                field_type="float" if val_f is not None else "string",
                timestamp=receive_time, persist=False, is_schema_defined=False
            ))
        return results

    def _extract_field(self, payload: dict, field_def: FieldDef, timestamp: datetime) -> list[ExtractedValue]:
        path = field_def.path or f"$.{field_def.name}"
        if path.startswith("$.") and "." not in path[2:] and "[" not in path:
            key = path[2:]
            if key in payload: raw_value = payload[key]
            else: return []
        else:
            try:
                expr = _get_jsonpath(path)
                matches = expr.find(payload)
            except Exception as e:
                logger.warning("JSONPath %s error: %s", path, e)
                return []
            if not matches: return []
            raw_value = [m.value for m in matches] if len(matches) > 1 else matches[0].value

        if isinstance(raw_value, list):
            return self._handle_array(raw_value, field_def, timestamp)

        val_f, val_t, val_j = _coerce_value(raw_value, field_def.type)
        return [ExtractedValue(
            field_name=field_def.name, tag_suffix=field_def.name,
            value=val_f, value_text=val_t, value_json=val_j,
            field_type=field_def.type, unit=field_def.unit,
            deadband=field_def.deadband, timestamp=timestamp,
            persist=field_def.persist, target_column=field_def.target_column,
        )]

    def _handle_array(self, values: list, field_def: FieldDef, timestamp: datetime) -> list[ExtractedValue]:
        if not values: return []
        mode = field_def.array_mode
        if mode == "single" or mode == "last":
            raw = values[0] if mode == "single" else values[-1]
            val_f, val_t, val_j = _coerce_value(raw, field_def.type)
            return [ExtractedValue(
                field_name=field_def.name, tag_suffix=field_def.name,
                value=val_f, value_text=val_t, value_json=val_j,
                field_type=field_def.type, unit=field_def.unit,
                deadband=field_def.deadband, timestamp=timestamp,
                persist=field_def.persist, target_column=field_def.target_column
            )]
        elif mode == "avg":
            numeric = [float(v) for v in values if isinstance(v, (int, float, str))]
            if not numeric: return []
            return [ExtractedValue(
                field_name=field_def.name, tag_suffix=field_def.name,
                value=sum(numeric)/len(numeric), field_type=field_def.type,
                unit=field_def.unit, deadband=field_def.deadband,
                timestamp=timestamp, persist=field_def.persist, target_column=field_def.target_column
            )]
        elif mode == "expand":
            results = []
            for i, raw in enumerate(values):
                val_f, val_t, val_j = _coerce_value(raw, field_def.type)
                results.append(ExtractedValue(
                    field_name=f"{field_def.name}[{i}]", tag_suffix=f"{field_def.name}_{i}",
                    value=val_f, value_text=val_t, value_json=val_j,
                    field_type=field_def.type, unit=field_def.unit,
                    deadband=field_def.deadband, timestamp=timestamp,
                    persist=field_def.persist, target_column=field_def.target_column
                ))
            return results
        return []
