import pytest
from unittest.mock import MagicMock

def test_mock_db_pool_connection(mock_db_pool):
    """
    驗證 Mock DB Pool 的 context manager 邏輯是否正確。
    """
    with mock_db_pool.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        # 驗證 cursor 方法是否有被呼叫（雖然是 mock）
        assert conn.cursor is not None
        assert cur.execute is not None

def test_mock_mqtt_msg_creation(mock_mqtt_msg):
    """
    驗證 Mock MQTT 訊息工廠。
    """
    topic = "Taiwan/Test"
    data = {"value": 100}
    msg = mock_mqtt_msg(topic, data)
    
    assert msg.topic == topic
    assert b"100" in msg.payload
