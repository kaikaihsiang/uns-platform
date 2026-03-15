import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.db_writer import (
    AlarmRecord,
    DBWriter,
    EventRecord,
    MeasurementRecord,
    MetricsRecord,
    RawPayloadRecord,
    StatusRecord,
    TelemetryRecord,
)


@pytest.fixture
def db_writer(mock_db_pool):
    """建立一個測試用的 DBWriter，設定較小的 batch size 以便測試。"""
    return DBWriter(db_pool=mock_db_pool, batch_size=5, batch_interval_sec=0.1)


def test_db_writer_batch_trigger(db_writer, mock_db_pool):
    """驗證當達到 BATCH_SIZE 時，會自動觸發 flush。"""
    # 取得 mock connection 並將 cursor 替換為 MagicMock
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    mock_conn.cursor = MagicMock()

    with patch("src.db_writer.execute_values") as mock_execute_values:
        # 新增 4 筆資料 (未滿 5 筆)
        for i in range(4):
            db_writer.add_telemetry(
                TelemetryRecord(time=datetime.now(timezone.utc), tag_id=1, value=10.0 + i)
            )

        assert db_writer.stats["telemetry_buffer"] == 4
        assert mock_execute_values.call_count == 0

        # 新增第 5 筆，觸發 flush
        db_writer.add_telemetry(
            TelemetryRecord(time=datetime.now(timezone.utc), tag_id=1, value=14.0)
        )

        assert db_writer.stats["telemetry_buffer"] == 0
        # Only 1 call: telemetry flush. latest_values is only flushed on tick() or manual flush()
        assert mock_execute_values.call_count == 1
        assert db_writer.stats["telemetry_written"] == 5


def test_db_writer_time_trigger(db_writer, mock_db_pool):
    """驗證當時間超過 batch_interval 時，tick() 會觸發 flush。"""
    # 確保 cursor 是可用的
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    mock_conn.cursor = MagicMock()

    with patch("src.db_writer.execute_values") as mock_execute_values:
        db_writer.add_telemetry(
            TelemetryRecord(time=datetime.now(timezone.utc), tag_id=1, value=10.0)
        )
        assert db_writer.stats["telemetry_buffer"] == 1

        # 模擬時間流逝
        time.sleep(0.15)
        db_writer.tick()

        assert db_writer.stats["telemetry_buffer"] == 0
        # Now 2 calls: 1 for telemetry, 1 for latest_values
        assert mock_execute_values.call_count == 2


def test_db_writer_multi_category_flush(db_writer, mock_db_pool):
    """驗證不同類別的資料都能正確 flush 到各自的表。"""
    now = datetime.now(timezone.utc)

    db_writer.add_status(StatusRecord(time=now, tag_id=2, state_code="RUN"))
    db_writer.add_alarm(AlarmRecord(time=now, tag_id=3, alarm_id="A1", alarm_code="E01"))
    db_writer.add_event(EventRecord(time=now, tag_id=4, event_id="E1", event_code="START"))
    db_writer.add_measurement(MeasurementRecord(time=now, tag_id=5, value=1.23))
    db_writer.add_metrics(MetricsRecord(time=now, tag_id=6, metric_category="OEE", metric_code="KPI"))
    db_writer.add_raw_payload(RawPayloadRecord(time=now, topic="test/topic", payload={"raw": 1}))

    assert db_writer.stats["status_buffer"] == 1
    assert db_writer.stats["alarm_buffer"] == 1
    assert db_writer.stats["event_buffer"] == 1
    assert db_writer.stats["meas_buffer"] == 1
    assert db_writer.stats["raw_buffer"] == 1

    with patch("src.db_writer.execute_values") as mock_execute_values:
        db_writer.flush()
        # 總共 7 種不同表 (status, alarm, event, metrics, meas, raw, latest_values)
        # 注意：flush() 會呼叫所有 _flush_* 方法
        assert mock_execute_values.call_count == 7
        assert db_writer.stats["telemetry_buffer"] == 0
        assert db_writer.stats["raw_written"] == 1


def test_db_writer_error_handling(db_writer, mock_db_pool):
    """驗證當資料庫寫入失敗時，錯誤統計會增加。"""
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    
    with patch.object(mock_conn, "cursor", side_effect=Exception("DB Connection Lost")):
        db_writer.add_telemetry(
            TelemetryRecord(time=datetime.now(timezone.utc), tag_id=1, value=10.0)
        )

        db_writer.flush()

    # Now 3 errors: telemetry flush, latest values flush, last_data_at update
    assert db_writer.stats["errors"] == 3
    # 即使失敗，buffer 也應該清空，避免無限重試卡死 Pipeline
    assert db_writer.stats["telemetry_buffer"] == 0


def test_db_writer_graceful_shutdown(db_writer, mock_db_pool):
    """驗證 close() 時會強制 flush。"""
    db_writer.add_telemetry(
        TelemetryRecord(time=datetime.now(timezone.utc), tag_id=1, value=10.0)
    )

    with patch.object(db_writer, "flush", wraps=db_writer.flush) as mock_flush:
        db_writer.close()
        assert mock_flush.call_count == 1


def test_db_writer_last_data_at_flush(db_writer, mock_db_pool):
    """驗證 flush 時會批次更新 tags.last_data_at。"""
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value
    mock_conn.cursor = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # 新增一些資料以記錄 Tag ID
    db_writer.add_telemetry(TelemetryRecord(time=datetime.now(timezone.utc), tag_id=10, value=1.0))
    db_writer.add_telemetry(TelemetryRecord(time=datetime.now(timezone.utc), tag_id=20, value=2.0))
    db_writer.add_telemetry(TelemetryRecord(time=datetime.now(timezone.utc), tag_id=10, value=3.0)) # 重複 ID 應被 set 去重

    with patch("src.db_writer.execute_values"):
        db_writer.flush()

    # 驗證是否執行了 UPDATE tags ... WHERE tag_id IN ...
    # 我們檢查 execute 呼叫中的 SQL
    update_calls = [call for call in mock_cursor.execute.call_args_list if "UPDATE tags SET last_data_at" in call[0][0]]
    assert len(update_calls) == 1
    
    # 檢查傳入的參數 (tag_id tuple)
    params = update_calls[0][0][1]
    assert sorted(params[0]) == [10, 20]
