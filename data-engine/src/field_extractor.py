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
        "field_type", "unit", "deadband", "timestamp", "persist",
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
                    # Unix timestamp（秒或毫秒）
                    if raw_ts > 1e12:
                        raw_ts = raw_ts / 1000.0
                    return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                elif isinstance(raw_ts, str):
                    # ISO 8601 字串
                    # 嘗試多種格式
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
    """
    依 field_type 強制轉型。
    Returns: (value_float, value_text, value_json)
    """
    if field_type in ("float", "integer"):
        try:
            return (float(raw_value), None, None)
        except (TypeError, ValueError):
            logger.warning("Cannot cast %r to float, storing as text", raw_value)
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
        # 未知型別，嘗試 float
        try:
            return (float(raw_value), None, None)
        except (TypeError, ValueError):
            return (None, str(raw_value), None)


class FieldExtractor:
    """
    從 payload 中依 Schema Type fields 定義取值。

    使用方式：
        extractor = FieldExtractor()
        values = extractor.extract(payload, schema_match, receive_time)
    """

    def extract(
        self,
        payload: dict,
        schema: SchemaMatch,
        receive_time: Optional[datetime] = None,
    ) -> list[ExtractedValue]:
        """
        從 payload 根據 schema.fields 定義取值。

        Args:
            payload: 已 decode 的 dict
            schema: SchemaMatch（含 fields 定義）
            receive_time: MQTT 收到的時間（fallback timestamp）

        Returns:
            list of ExtractedValue
        """
        if receive_time is None:
            receive_time = datetime.now(timezone.utc)

        timestamp = _extract_timestamp(payload, schema.timestamp_field, receive_time)
        results = []

        for field_def in schema.fields:
            if not field_def.extract:
                continue

            extracted = self._extract_field(payload, field_def, timestamp)
            if extracted:
                results.extend(extracted)

        return results

    def extract_flat(
        self,
        payload: dict,
        receive_time: Optional[datetime] = None,
    ) -> list[ExtractedValue]:
        """
        無 Schema Type 時的 fallback：把 payload 的每個 top-level key 各自取值。
        僅於 auto-detect 流程使用（Phase 1 不寫 DB，只存 raw）。
        """
        if receive_time is None:
            receive_time = datetime.now(timezone.utc)

        results = []
        for key, raw_value in payload.items():
            if key.startswith("_"):  # 跳過 _meta 等內部欄位
                continue
            val_float, val_text, val_json = _coerce_value(raw_value, "float")
            results.append(ExtractedValue(
                field_name=key,
                tag_suffix=key,
                value=val_float,
                value_text=val_text,
                value_json=val_json,
                field_type="float" if val_float is not None else "string",
                timestamp=receive_time,
                persist=False,  # auto-detect 暫不寫 DB
            ))
        return results

    def _extract_field(
        self,
        payload: dict,
        field_def: FieldDef,
        timestamp: datetime,
    ) -> list[ExtractedValue]:
        """取單一欄位的值。"""
        path = field_def.path or f"$.{field_def.name}"

        # 簡化路徑：對於 L1/L2（直接 key），不需要 jsonpath
        if path.startswith("$.") and "." not in path[2:] and "[" not in path:
            key = path[2:]
            if key in payload:
                raw_value = payload[key]
            else:
                return []
        else:
            # JSONPath 解析
            try:
                expr = _get_jsonpath(path)
                matches = expr.find(payload)
            except Exception as e:
                logger.warning("JSONPath %s error: %s", path, e)
                return []

            if not matches:
                return []

            if len(matches) > 1:
                # 陣列結果
                return self._handle_array(
                    [m.value for m in matches], field_def, timestamp
                )

            raw_value = matches[0].value

        # 如果是 list 且有多個值
        if isinstance(raw_value, list):
            return self._handle_array(raw_value, field_def, timestamp)

        # 單值
        val_float, val_text, val_json = _coerce_value(raw_value, field_def.type)
        return [ExtractedValue(
            field_name=field_def.name,
            tag_suffix=field_def.name,
            value=val_float,
            value_text=val_text,
            value_json=val_json,
            field_type=field_def.type,
            unit=field_def.unit,
            deadband=field_def.deadband,
            timestamp=timestamp,
            persist=field_def.persist,
        )]

    def _handle_array(
        self,
        values: list,
        field_def: FieldDef,
        timestamp: datetime,
    ) -> list[ExtractedValue]:
        """處理陣列結果（依 array_mode 策略）。"""
        if not values:
            return []

        mode = field_def.array_mode

        if mode == "single":
            raw = values[0]
            val_f, val_t, val_j = _coerce_value(raw, field_def.type)
            return [ExtractedValue(
                field_name=field_def.name,
                tag_suffix=field_def.name,
                value=val_f,
                value_text=val_t,
                value_json=val_j,
                field_type=field_def.type,
                unit=field_def.unit,
                deadband=field_def.deadband,
                timestamp=timestamp,
                persist=field_def.persist,
            )]

        elif mode == "last":
            raw = values[-1]
            val_f, val_t, val_j = _coerce_value(raw, field_def.type)
            return [ExtractedValue(
                field_name=field_def.name,
                tag_suffix=field_def.name,
                value=val_f,
                value_text=val_t,
                value_json=val_j,
                field_type=field_def.type,
                unit=field_def.unit,
                deadband=field_def.deadband,
                timestamp=timestamp,
                persist=field_def.persist,
            )]

        elif mode == "avg":
            numeric = []
            for v in values:
                try:
                    numeric.append(float(v))
                except (TypeError, ValueError):
                    pass
            if not numeric:
                return []
            avg_val = sum(numeric) / len(numeric)
            return [ExtractedValue(
                field_name=field_def.name,
                tag_suffix=field_def.name,
                value=avg_val,
                field_type=field_def.type,
                unit=field_def.unit,
                deadband=field_def.deadband,
                timestamp=timestamp,
                persist=field_def.persist,
            )]

        elif mode == "expand":
            results = []
            for i, raw in enumerate(values):
                val_f, val_t, val_j = _coerce_value(raw, field_def.type)
                results.append(ExtractedValue(
                    field_name=f"{field_def.name}[{i}]",
                    tag_suffix=f"{field_def.name}_{i}",
                    value=val_f,
                    value_text=val_t,
                    value_json=val_j,
                    field_type=field_def.type,
                    unit=field_def.unit,
                    deadband=field_def.deadband,
                    timestamp=timestamp,
                    persist=field_def.persist,
                ))
            return results

        else:
            logger.warning("Unknown array_mode: %s", mode)
            return []
