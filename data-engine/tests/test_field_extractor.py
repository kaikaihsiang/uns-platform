import pytest
import json
from datetime import datetime, timezone
from src.field_extractor import FieldExtractor
from src.schema_matcher import SchemaMatch, FieldDef

@pytest.fixture
def extractor():
    return FieldExtractor()

@pytest.fixture
def sample_payloads():
    with open("../docs/payload_samples.json", "r") as f:
        return json.load(f)

def test_extract_telemetry_nested(extractor, sample_payloads):
    """
    驗證從 SMT-Mounter-01/Telemetry 中提取巢狀數值。
    """
    topic = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Telemetry"
    payload = sample_payloads[topic]
    
    # 定義 Schema
    schema = SchemaMatch(
        node_id=1,
        full_path=topic,
        persist_mode="db",
        retention_days=90,
        timestamp_field="$._meta.timestamp",
        fields=[
            FieldDef(name="temperature", path="$.data.values.temp", type="float", unit="C"),
            FieldDef(name="pressure", path="$.data.values.press", type="float", unit="kPa")
        ]
    )
    
    results = extractor.extract(payload, schema)
    
    assert len(results) >= 2
    temp_val = next(r for r in results if r.field_name == "temperature")
    assert temp_val.value == 25.5
    assert temp_val.unit == "C"
    assert temp_val.timestamp == datetime(2023, 10, 27, 10, 0, 0, tzinfo=timezone.utc)

def test_extract_status_with_target_mapping(extractor, sample_payloads):
    """
    驗證 Status 類別的 target_column 映射。
    """
    topic = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Status"
    payload = sample_payloads[topic]
    
    schema = SchemaMatch(
        node_id=2,
        full_path=topic,
        persist_mode="db",
        retention_days=90,
        schema_category="status",
        fields=[
            FieldDef(name="state", path="$.data.state_code", type="string", target_column="state_code"),
            FieldDef(name="mode", path="$.data.mode", type="string", target_column="mode")
        ]
    )
    
    results = extractor.extract(payload, schema)
    
    state_val = next(r for r in results if r.field_name == "state")
    assert state_val.value_text == "PRODUCTION"
    assert state_val.target_column == "state_code"

def test_extract_unknown_fields_flat_data(extractor):
    """
    驗證當 payload["data"] 是扁平結構且未定義 Schema 時，能否自動捕捉。
    """
    payload = {
        "data": {
            "known": 100,
            "unknown": 200
        }
    }
    schema = SchemaMatch(
        node_id=1, full_path="test", persist_mode="db", retention_days=90,
        fields=[FieldDef(name="known", path="$.data.known", type="float")]
    )
    
    results = extractor.extract(payload, schema)
    
    # 應該有 1 個 schema_defined (known) 和 1 個自動捕捉 (unknown)
    assert len(results) == 2
    unknown_val = next(r for r in results if r.field_name == "unknown")
    assert unknown_val.is_schema_defined is False
    assert unknown_val.value == 200.0
