from unittest.mock import MagicMock

import pytest
from src.category_router import CategoryRouter


@pytest.fixture
def router():
    return CategoryRouter()

@pytest.fixture
def mock_schema():
    """建立一個 Mock 的 SchemaMatch 物件。"""
    schema = MagicMock()
    schema.schema_name = "TestSchema"
    schema.schema_category = "telemetry"
    schema.full_path = "Enterprise/Site/Area/Line/Equipment/Telemetry"
    return schema

def test_router_priority_1_schema_defined(router, mock_schema):
    """優先級 1：Schema 明確定義了非 telemetry 的類別。"""
    mock_schema.schema_category = "alarm"
    mock_schema.full_path = "Any/Path/Telemetry" # 雖然 Topic 是 Telemetry，但 Schema 優先
    
    assert router.resolve(mock_schema) == "alarm"

def test_router_priority_2_topic_fallback(router, mock_schema):
    """優先級 2：Schema 為 telemetry，但 Topic 最後一段是特定類別。"""
    mock_schema.schema_category = "telemetry"
    mock_schema.full_path = "Enterprise/Site/Area/Line/Equipment/Status"
    
    assert router.resolve(mock_schema) == "status"

def test_router_priority_3_default_telemetry(router, mock_schema):
    """優先級 3：無明確定義且 Topic 無法辨識，預設為 telemetry。"""
    mock_schema.schema_category = "telemetry"
    mock_schema.full_path = "Enterprise/Site/Area/Line/Equipment/Unknown"
    
    assert router.resolve(mock_schema) == "telemetry"

def test_router_invalid_category_fallback(router, mock_schema):
    """當 Schema 定義了無效類別時，應 Fallback 到 Topic 或預設。"""
    mock_schema.schema_category = "invalid_cat"
    mock_schema.full_path = "Enterprise/Site/Area/Line/Equipment/Alarm"
    
    assert router.resolve(mock_schema) == "alarm"

def test_router_case_insensitivity(router, mock_schema):
    """Topic Fallback 應該是不分大小寫的。"""
    mock_schema.schema_category = "telemetry"
    mock_schema.full_path = "Enterprise/Site/Area/Line/Equipment/MEASUREMENT"
    
    assert router.resolve(mock_schema) == "measurement"
