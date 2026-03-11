import pytest
from src.auto_detect import AutoDetector


@pytest.fixture
def detector():
    # Set threshold to 2 for faster unit testing
    return AutoDetector(threshold=2)

def test_flatten_json_basic(detector):
    """驗證基本的 JSON 展開與 JSONPath 生成。"""
    payload = {
        "temperature": 25.5,
        "status": "OK"
    }
    fields = detector._flatten_json(payload)
    
    # 預期路徑：$.temperature, $.status
    paths = [f["path"] for f in fields]
    assert "$.temperature" in paths
    assert "$.status" in paths
    
    temp_field = next(f for f in fields if f["path"] == "$.temperature")
    assert temp_field["type"] == "float"

def test_flatten_json_recursive(detector):
    """驗證遞迴展開巢狀 JSON。"""
    payload = {
        "data": {
            "values": {
                "temp": 25.5,
                "press": 101.3
            },
            "device_id": "DEV-001"
        }
    }
    fields = detector._flatten_json(payload)
    
    paths = [f["path"] for f in fields]
    assert "$.data.values.temp" in paths
    assert "$.data.values.press" in paths
    assert "$.data.device_id" in paths
    
    temp_field = next(f for f in fields if f["path"] == "$.data.values.temp")
    assert temp_field["type"] == "float"
    assert temp_field["name"] == "temp"

def test_collect_samples_and_infer(detector):
    """驗證樣本收集與推斷觸發邏輯。"""
    topic = "Taiwan/Line1/Telemetry"
    
    # 樣本 1
    res1 = detector.collect_sample(topic, {"a": 1})
    assert res1 is None
    
    # 樣本 2 (達到門檻 2)
    res2 = detector.collect_sample(topic, {"b": 2})
    assert res2 is not None
    
    # 驗證推斷結果包含合併後的欄位
    definition = res2["definition"]
    field_names = [f["name"] for f in definition]
    assert "a" in field_names
    assert "b" in field_names
    assert res2["topic_pattern"] == topic

def test_type_detection(detector):
    """驗證型別偵測。"""
    assert detector._get_type(True) == "boolean"
    assert detector._get_type(100) == "integer"
    assert detector._get_type(100.5) == "float"
    assert detector._get_type("hello") == "string"
    assert detector._get_type({"x": 1}) == "json"
    assert detector._get_type([1, 2, 3]) == "array"
