
import pytest
from src.field_extractor import FieldExtractor
from src.schema_matcher import FieldDef


@pytest.fixture
def extractor():
    return FieldExtractor()

@pytest.fixture
def base_schema():
    """建立一個基本的 SchemaMatch，定義一個 telemetry 欄位。"""
    schema = MagicMock()
    schema.schema_name = "RobustTest"
    schema.timestamp_field = None
    
    # 定義一個明確映射到 value 的欄位
    f1 = FieldDef(name="temp", path="$.data.temp", type="float", target_column="value")
    # 定義一個沒有指定 target_column 的欄位 (預期進入 overflow)
    f2 = FieldDef(name="pressure", path="$.data.pressure", type="float", target_column=None)
    
    schema.fields = [f1, f2]
    return schema

from unittest.mock import MagicMock


def test_field_extractor_overflow_detection(extractor, base_schema):
    """驗證未定義欄位與無目標欄位映射的溢位偵測。"""
    payload = {
        "data": {
            "temp": 25.5,          # 已定義，target=value
            "pressure": 1.2,      # 已定義，target=None (overflow)
            "humidity": 60.0,     # 未定義 (overflow)
            "status_msg": "OK"    # 未定義 (overflow)
        }
    }
    
    results = extractor.extract(payload, base_schema)
    
    # 預期結果數量：2 (定義) + 2 (未定義) = 4
    assert len(results) == 4
    
    # 檢查 temp (不應是 overflow)
    temp_ev = next(r for r in results if r.field_name == "temp")
    assert temp_ev.overflow is False
    assert temp_ev.value == 25.5
    
    # 檢查 pressure (定義但無目標，應是 overflow)
    press_ev = next(r for r in results if r.field_name == "pressure")
    assert press_ev.overflow is True
    assert press_ev.value == 1.2
    
    # 檢查 humidity (未定義，應是 overflow)
    hum_ev = next(r for r in results if r.field_name == "humidity")
    assert hum_ev.overflow is True
    assert hum_ev.is_schema_defined is False
    assert hum_ev.value == 60.0

def test_field_extractor_type_mismatch_resilience(extractor, base_schema):
    """驗證型別不符時的強制轉型與保留。"""
    # 修改 Schema，定義一個 float 欄位
    f_float = FieldDef(name="speed", path="$.data.speed", type="float", target_column="value")
    base_schema.fields = [f_float]
    
    # Payload 中 speed 給字串 "FAST"
    payload = {
        "data": {
            "speed": "FAST"
        }
    }
    
    results = extractor.extract(payload, base_schema)
    speed_ev = results[0]
    
    # 雖然型別不符，但不應崩潰。value 應為 None，但文字應保留在 value_text
    assert speed_ev.value is None
    assert speed_ev.value_text == "FAST"

def test_field_extractor_nested_data_capture(extractor, base_schema):
    """驗證 data 區塊內的巢狀結構也能被捕捉為 overflow。"""
    base_schema.fields = [] # 完全不定義欄位
    
    payload = {
        "data": {
            "nested": {"a": 1, "b": 2},
            "array": [1, 2, 3]
        }
    }
    
    results = extractor.extract(payload, base_schema)
    
    # 應捕捉到 2 個 overflow 欄位
    assert len(results) == 2
    
    nested_ev = next(r for r in results if r.field_name == "nested")
    assert nested_ev.overflow is True
    assert nested_ev.value_json == {"a": 1, "b": 2}
    assert nested_ev.field_type == "json"
