import json
from datetime import datetime, timezone

import pytest
from src.field_extractor import FieldExtractor
from src.schema_matcher import FieldDef, SchemaMatch


@pytest.fixture
def extractor():
    return FieldExtractor()

@pytest.fixture
def sample_payloads():
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "../../docs/payload_samples.json")
    with open(path, "r") as f:
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


def test_overflow_marking(extractor):
    """
    驗證 FieldExtractor 的 overflow 標記邏輯。
    """
    payload = {
        "data": {
            "mapped_col": "STATE-01",
            "mapped_details": "RECP-123",
            "unmapped": 456,
            "unknown": 789
        }
    }
    schema = SchemaMatch(
        node_id=1, full_path="test/event", persist_mode="db", retention_days=30,
        schema_category="event",
        fields=[
            # 1. 映射到實體欄位 -> overflow 應為 False
            FieldDef(name="mapped_col", path="$.data.mapped_col", type="string", target_column="event_code"),
            # 2. 映射到 details -> overflow 應為 True
            FieldDef(name="mapped_details", path="$.data.mapped_details", type="string", target_column="details"),
            # 3. 定義但未映射 -> overflow 應為 True
            FieldDef(name="unmapped", path="$.data.unmapped", type="float", target_column=None)
        ]
    )
    
    results = extractor.extract(payload, schema)
    
    # 預期結果：
    # - mapped_col: overflow=False
    # - mapped_details: overflow=True
    # - unmapped: overflow=True
    # - unknown: overflow=True (自動捕捉)
    
    col_val = next(r for r in results if r.field_name == "mapped_col")
    assert col_val.overflow is False
    
    details_val = next(r for r in results if r.field_name == "mapped_details")
    assert details_val.overflow is True
    
    unmapped_val = next(r for r in results if r.field_name == "unmapped")
    assert unmapped_val.overflow is True
    
    unknown_val = next(r for r in results if r.field_name == "unknown")
    assert unknown_val.overflow is True
    assert unknown_val.is_schema_defined is False


def test_extract_array_modes(extractor):
    """
    驗證不同的 array_mode 處理邏輯。
    """
    payload = {
        "data": {
            "temps": [20.0, 22.0, 24.0]
        }
    }
    
    # 1. Mode: single (取第一個)
    schema_single = SchemaMatch(
        node_id=1, full_path="test", persist_mode="db", retention_days=30,
        fields=[FieldDef(name="t", path="$.data.temps", type="float", array_mode="single")]
    )
    res_single = extractor.extract(payload, schema_single)
    assert len(res_single) == 1
    assert res_single[0].value == 20.0

    # 2. Mode: avg (取平均)
    schema_avg = SchemaMatch(
        node_id=1, full_path="test", persist_mode="db", retention_days=30,
        fields=[FieldDef(name="t", path="$.data.temps", type="float", array_mode="avg")]
    )
    res_avg = extractor.extract(payload, schema_avg)
    assert res_avg[0].value == 22.0

    # 3. Mode: expand (展開)
    schema_expand = SchemaMatch(
        node_id=1, full_path="test", persist_mode="db", retention_days=30,
        fields=[FieldDef(name="t", path="$.data.temps", type="float", array_mode="expand")]
    )
    res_expand = extractor.extract(payload, schema_expand)
    assert len(res_expand) == 3
    assert res_expand[0].value == 20.0
    assert res_expand[1].value == 22.0
    assert res_expand[2].value == 24.0
    assert res_expand[1].field_name == "t[1]"
    assert res_expand[1].tag_suffix == "t_1"

