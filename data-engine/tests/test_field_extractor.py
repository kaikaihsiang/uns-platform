"""
Tests for UNS Data Engine — Field Extractor
"""

from datetime import datetime, timezone

from src.field_extractor import FieldExtractor, _extract_timestamp, _coerce_value
from src.schema_matcher import FieldDef, SchemaMatch


class TestCoerceValue:
    """型別轉換測試。"""

    def test_float_from_float(self):
        assert _coerce_value(25.3, "float") == (25.3, None, None)

    def test_float_from_int(self):
        assert _coerce_value(25, "float") == (25.0, None, None)

    def test_float_from_string_number(self):
        assert _coerce_value("25.3", "float") == (25.3, None, None)

    def test_float_from_invalid_string(self):
        val_f, val_t, val_j = _coerce_value("not_a_number", "float")
        assert val_f is None
        assert val_t == "not_a_number"

    def test_string_type(self):
        val_f, val_t, val_j = _coerce_value("running", "string")
        assert val_f is None
        assert val_t == "running"

    def test_boolean_true(self):
        val_f, val_t, val_j = _coerce_value(True, "boolean")
        assert val_f == 1.0

    def test_boolean_false(self):
        val_f, val_t, val_j = _coerce_value(False, "boolean")
        assert val_f == 0.0

    def test_json_type(self):
        data = {"nested": {"key": "value"}}
        val_f, val_t, val_j = _coerce_value(data, "json")
        assert val_f is None
        assert val_j == data


class TestTimestampExtraction:
    """Timestamp 取值測試。"""

    def test_no_timestamp_field(self):
        receive_time = datetime(2024, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
        result = _extract_timestamp({}, None, receive_time)
        assert result == receive_time

    def test_iso_timestamp_in_payload(self):
        payload = {"_meta": {"timestamp": "2024-01-15T08:30:00+00:00"}}
        receive_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        result = _extract_timestamp(payload, "$._meta.timestamp", receive_time)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 8
        assert result.minute == 30

    def test_unix_timestamp_seconds(self):
        payload = {"ts": 1705305000}  # 2024-01-15T08:30:00Z approx
        receive_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        result = _extract_timestamp(payload, "$.ts", receive_time)
        assert result.year == 2024

    def test_unix_timestamp_milliseconds(self):
        payload = {"ts": 1705305000000}  # milliseconds
        receive_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        result = _extract_timestamp(payload, "$.ts", receive_time)
        assert result.year == 2024

    def test_fallback_on_missing_field(self):
        """payload 沒有指定的 timestamp 欄位 → fallback。"""
        payload = {"temperature": 25.3}
        receive_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        result = _extract_timestamp(payload, "$._meta.timestamp", receive_time)
        assert result == receive_time


class TestFieldExtractor:
    """Field Extractor 測試。"""

    def setup_method(self):
        self.extractor = FieldExtractor()

    def _make_schema(self, fields, timestamp_field=None):
        return SchemaMatch(
            node_id=1,
            full_path="Test/Site/Line1/Printer/Telemetry",
            persist_mode="db",
            retention_days=90,
            schema_type_id=1,
            timestamp_field=timestamp_field,
            fields=[FieldDef(**f) for f in fields],
        )

    def test_l1_simple_payload(self):
        """L1 Simple: 單一 key-value。"""
        schema = self._make_schema([
            {"name": "value", "path": "$.value", "type": "float"},
        ])
        payload = {"value": 25.3}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].value == 25.3
        assert results[0].field_name == "value"

    def test_l2_flat_payload(self):
        """L2 Flat: 多個 key-value。"""
        schema = self._make_schema([
            {"name": "temperature", "path": "$.temperature", "type": "float", "unit": "°C", "deadband": 0.1},
            {"name": "pressure", "path": "$.pressure", "type": "float", "unit": "kPa", "deadband": 0.05},
        ])
        payload = {"temperature": 25.3, "pressure": 2.1}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 2
        assert results[0].value == 25.3
        assert results[0].unit == "°C"
        assert results[1].value == 2.1

    def test_missing_field(self):
        """payload 中缺少某欄位。"""
        schema = self._make_schema([
            {"name": "temperature", "path": "$.temperature", "type": "float"},
            {"name": "humidity", "path": "$.humidity", "type": "float"},
        ])
        payload = {"temperature": 25.3}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].field_name == "temperature"

    def test_extract_false_skipped(self):
        """extract=false 的欄位被跳過。"""
        schema = self._make_schema([
            {"name": "temperature", "path": "$.temperature", "type": "float", "extract": True},
            {"name": "raw_data", "path": "$.raw_data", "type": "json", "extract": False},
        ])
        payload = {"temperature": 25.3, "raw_data": {"key": "val"}}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1

    def test_persist_false_marked(self):
        """persist=false 的欄位仍然 extract 但 persist 標記為 False。"""
        schema = self._make_schema([
            {"name": "humidity", "path": "$.humidity", "type": "float", "persist": False},
        ])
        payload = {"humidity": 65.0}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].persist is False

    def test_string_field(self):
        """字串型別欄位。"""
        schema = self._make_schema([
            {"name": "recipe_name", "path": "$.recipe_name", "type": "string"},
        ])
        payload = {"recipe_name": "Recipe_A"}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].value_text == "Recipe_A"
        assert results[0].value is None

    def test_timestamp_from_payload(self):
        """從 payload 取 timestamp。"""
        schema = self._make_schema(
            fields=[{"name": "temperature", "path": "$.temperature", "type": "float"}],
            timestamp_field="$._meta.timestamp",
        )
        payload = {
            "_meta": {"timestamp": "2024-01-15T08:30:00+00:00"},
            "temperature": 25.3,
        }
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].timestamp.hour == 8
        assert results[0].timestamp.minute == 30

    def test_array_mode_avg(self):
        """array_mode=avg：取平均值。"""
        schema = self._make_schema([
            {"name": "temp", "path": "$.temps", "type": "float", "array_mode": "avg"},
        ])
        payload = {"temps": [20.0, 25.0, 30.0]}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].value == 25.0

    def test_array_mode_last(self):
        """array_mode=last：取最後一個值。"""
        schema = self._make_schema([
            {"name": "temp", "path": "$.temps", "type": "float", "array_mode": "last"},
        ])
        payload = {"temps": [20.0, 25.0, 30.0]}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 1
        assert results[0].value == 30.0

    def test_array_mode_expand(self):
        """array_mode=expand：展開為多筆。"""
        schema = self._make_schema([
            {"name": "temp", "path": "$.temps", "type": "float", "array_mode": "expand"},
        ])
        payload = {"temps": [20.0, 25.0, 30.0]}
        results = self.extractor.extract(payload, schema)
        assert len(results) == 3
        assert results[0].value == 20.0
        assert results[1].value == 25.0
        assert results[2].value == 30.0
        assert results[0].tag_suffix == "temp_0"
        assert results[2].tag_suffix == "temp_2"

    def test_extract_flat_without_schema(self):
        """無 Schema Type 時的 fallback。"""
        payload = {"temperature": 25.3, "pressure": 2.1, "_meta": {"ts": 123}}
        results = self.extractor.extract_flat(payload)
        assert len(results) == 2  # _meta 被跳過
        names = {r.field_name for r in results}
        assert "temperature" in names
        assert "pressure" in names
        assert all(not r.persist for r in results)  # auto-detect 不直接 persist
