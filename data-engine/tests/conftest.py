import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from src.db_pool import DBPool

# --- Mock DB Infrastructure (for unit tests) ---

class MockCursor:
    def __init__(self):
        self.description = []
        self.rowcount = 0
    def execute(self, sql, params=None): pass
    def fetchone(self): return None
    def fetchall(self): return []
    def close(self): pass

class MockConnection:
    def cursor(self): return MockCursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass

@pytest.fixture
def mock_db_pool():
    """Mock database pool that avoids real connections."""
    pool = MagicMock()
    mock_conn = MockConnection()
    pool.connection.return_value.__enter__.return_value = mock_conn
    return pool

# --- Real Test DB Infrastructure (for integration tests) ---

@pytest.fixture(scope="session")
def test_db_config():
    """Environment config for the test database."""
    return {
        "host": "localhost",
        "port": 5432,
        "dbname": "uns_test",
        "user": "uns_admin",
        "password": "uns_dev_password"
    }

@pytest.fixture
def real_db_pool(test_db_config):
    """Provides a real DBPool pointing to uns_test, with automatic cleanup."""
    import os
    from src.config import Config
    from src.db_pool import DBPool
    
    # 關鍵修正：在初始化 DBPool 前強行覆蓋類別屬性
    Config.DB_NAME = "uns_test"
    os.environ["DB_NAME"] = "uns_test"
    
    pool = DBPool()
    
    # Cleanup before test
    with pool.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT truncate_all_tables_test();")
        conn.commit()
        cur.close()
        
    yield pool
    pool.close()

# --- Mock MQTT Message ---

@pytest.fixture
def mock_mqtt_msg():
    """Factory for creating mock MQTT messages."""
    def _create(topic, payload_dict):
        msg = MagicMock()
        msg.topic = topic
        msg.payload = json.dumps(payload_dict).encode('utf-8')
        return msg
    return _create

# --- Common Fixtures ---

@pytest.fixture
def sample_time():
    """Stable timestamp for testing."""
    return datetime(2026, 3, 9, 12, 0, 0, tzinfo=timezone.utc)

@pytest.fixture
def sample_payloads():
    """Load standard payloads for testing."""
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "../../docs/payload_samples.json")
    with open(path, "r") as f:
        return json.load(f)
