from unittest.mock import MagicMock

import pytest
from src.context_cache import ActiveRunCache
from src.master_data_cache import MasterDataCache


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    return pool

def test_master_data_cache_resilience(mock_db_pool):
    """驗證 MasterDataCache 在 DB 失敗時仍保留舊資料。"""
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    mock_cursor = mock_conn.cursor.return_value
    
    # 第一次成功載入
    mock_cursor.fetchall.return_value = [
        ("status", "RUN", "", "Running", {})
    ]
    
    cache = MasterDataCache(db_pool=mock_db_pool)
    assert cache.lookup("status", "RUN")["label"] == "Running"
    
    # 第二次失敗 (DB 斷線)
    mock_cursor.execute.side_effect = Exception("DB Down")
    cache.refresh(force=True) # 強制刷新
    
    # 驗證舊資料還在，沒有被清空
    assert cache.lookup("status", "RUN")["label"] == "Running"

def test_active_run_cache_walk_up(mock_db_pool):
    """驗證 ActiveRunCache 的向上查找 (Walk-up resolution) 邏輯。"""
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    mock_cursor = mock_conn.cursor.return_value
    
    # 模擬資料庫中有 Line1 的 Active Run，但沒有具體 Machine 的
    mock_cursor.fetchall.return_value = [
        ("Enterprise/Site/Area/Line1", 101, "LOT-A")
    ]
    
    cache = ActiveRunCache(db_pool=mock_db_pool)
    
    # 查詢具體 Machine，應自動關聯到 Line1 的 Lot
    context = cache.get_active_run("Enterprise/Site/Area/Line1/Machine1/SensorA")
    assert context is not None
    assert context["run_id"] == 101
    assert context["lot_id"] == "LOT-A"
    
    # 查詢不相關的路徑，應回傳 None
    assert cache.get_active_run("Enterprise/Site/Area/Line2/Machine1") is None

def test_active_run_cache_resilience(mock_db_pool):
    """驗證 ActiveRunCache 在 DB 失敗時仍保留舊資料。"""
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    mock_cursor = mock_conn.cursor.return_value
    
    mock_cursor.fetchall.return_value = [
        ("Line1", 101, "LOT-A")
    ]
    
    cache = ActiveRunCache(db_pool=mock_db_pool)
    assert cache.get_active_run("Line1")["lot_id"] == "LOT-A"
    
    # 失敗
    mock_cursor.execute.side_effect = Exception("DB Down")
    cache.refresh(force=True)
    
    assert cache.get_active_run("Line1")["lot_id"] == "LOT-A"
