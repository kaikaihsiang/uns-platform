"""
Tests for UNS Data Engine — Pipeline (end-to-end mock)
"""

import json
from unittest.mock import MagicMock

from src.db_writer import DBWriter
from src.deadband import DeadbandFilter
from src.field_extractor import FieldExtractor
from src.pipeline import Pipeline, TagLookup
from src.schema_matcher import FieldDef, SchemaMatch, SchemaMatcher


def _make_matcher(*matches: SchemaMatch) -> SchemaMatcher:
    matcher = SchemaMatcher()
    matcher.load_from_data(list(matches))
    return matcher


def _telemetry_schema(topic: str = "Ent/Site/Area/Line1/Printer/Telemetry") -> SchemaMatch:
    return SchemaMatch(
        node_id=1,
        full_path=topic,
        persist_mode="db",
        retention_days=90,
        schema_id=1,
        schema_name="Printer_Telemetry",
        decoder="json",
        timestamp_field=None,
        store_raw=True,
        fields=[
            FieldDef(name="temperature", path="$.temperature", type="float",
                     unit="°C", deadband=0.1),
            FieldDef(name="pressure", path="$.pressure", type="float",
                     unit="kPa"),
        ],
    )


class TestPipelineRouting:
    """Pipeline 路由測試：passthrough / retain / db。"""

    def test_passthrough_skipped(self):
        """passthrough topic → 不處理。"""
        matcher = _make_matcher(
            SchemaMatch(
                node_id=1,
                full_path="Ent/Site/Heartbeat",
                persist_mode="passthrough",
                retention_days=0,
            )
        )
        db_writer = MagicMock(spec=DBWriter)
        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )
        pipeline.process(
            "Ent/Site/Heartbeat",
            b'{"alive": true}',
        )
        db_writer.add_telemetry.assert_not_called()
        db_writer.add_raw_payload.assert_not_called()

    def test_retain_skipped(self):
        """retain topic → DB 不寫。"""
        matcher = _make_matcher(
            SchemaMatch(
                node_id=2,
                full_path="Ent/Site/Status",
                persist_mode="retain",
                retention_days=30,
            )
        )
        db_writer = MagicMock(spec=DBWriter)
        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )
        pipeline.process(
            "Ent/Site/Status",
            b'{"state": "running"}',
        )
        db_writer.add_telemetry.assert_not_called()
        db_writer.add_raw_payload.assert_not_called()

    def test_unknown_topic_skipped(self):
        """未註冊 topic → 跳過。"""
        matcher = SchemaMatcher()
        db_writer = MagicMock(spec=DBWriter)
        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )
        pipeline.process(
            "Unknown/Topic",
            b'{"value": 42}',
        )
        db_writer.add_telemetry.assert_not_called()


class TestPipelineDbPath:
    """Pipeline DB 路徑測試：decode → extract → deadband → write。"""

    def test_normal_telemetry_write(self):
        """正常 telemetry → 寫入 db_writer。"""
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )

        payload = json.dumps({"temperature": 25.3, "pressure": 2.1}).encode()
        pipeline.process(topic, payload)

        # 應寫入 2 筆 telemetry + 1 筆 raw
        assert db_writer.add_telemetry.call_count == 2
        assert db_writer.add_raw_payload.call_count == 1

    def test_deadband_filters_duplicates(self):
        """Deadband 過濾：同值連發只寫第一筆。"""
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
            deadband_filter=DeadbandFilter(enabled=True),
        )

        payload = json.dumps({"temperature": 25.0, "pressure": 2.0}).encode()

        # 發 10 次相同值
        for _ in range(10):
            pipeline.process(topic, payload)

        # temperature 有 deadband=0.1 → 只寫 1 筆
        # pressure 沒有 deadband → 每次都寫 = 10 筆
        # 總計 11 筆 telemetry
        assert db_writer.add_telemetry.call_count == 11

    def test_raw_payload_stored(self):
        """store_raw=True → raw payload 有寫。"""
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )

        payload = json.dumps({"temperature": 25.3}).encode()
        pipeline.process(topic, payload)

        assert db_writer.add_raw_payload.call_count == 1

    def test_store_raw_false(self):
        """store_raw=False → raw payload 不寫。"""
        topic = "Ent/Site/NoRaw/Telemetry"
        schema = SchemaMatch(
            node_id=5,
            full_path=topic,
            persist_mode="db",
            retention_days=90,
            store_raw=False,
            fields=[
                FieldDef(name="value", path="$.value", type="float"),
            ],
        )
        matcher = _make_matcher(schema)
        db_writer = MagicMock(spec=DBWriter)

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )

        payload = json.dumps({"value": 42.0}).encode()
        pipeline.process(topic, payload)

        assert db_writer.add_raw_payload.call_count == 0
        assert db_writer.add_telemetry.call_count == 1

    def test_invalid_json_skipped(self):
        """無法解碼的 payload → 跳過，不 crash。"""
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )

        pipeline.process(topic, b"not json")
        db_writer.add_telemetry.assert_not_called()
        db_writer.add_raw_payload.assert_not_called()


class TestPipelineStats:
    """Pipeline 統計測試。"""

    def test_stats_tracking(self):
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)
        db_writer.stats = {"telemetry_written": 0, "raw_written": 0, "errors": 0,
                           "telemetry_buffer": 0, "raw_buffer": 0}

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
        )

        payload = json.dumps({"temperature": 25.3}).encode()
        pipeline.process(topic, payload)
        pipeline.process("Unknown/Topic", b'{}')

        stats = pipeline.stats
        assert stats["total_processed"] == 2
        assert stats["total_no_schema"] == 1


class TestPipelineOverflow:
    """測試資料溢位至 details/context 的邏輯。"""

    def test_event_overflow_to_details(self):
        """驗證非 telemetry 資料會自動彙整 overflow 欄位至 details。"""
        topic = "Ent/Site/Area/Line1/Printer/Event/Recipe"
        schema = SchemaMatch(
            node_id=10,
            full_path=topic,
            persist_mode="db",
            retention_days=30,
            schema_category="event",
            fields=[
                FieldDef(name="event_code", path="$.event_code", type="string", target_column="event_code"),
                FieldDef(name="recipe_id", path="$.recipe_id", type="string", target_column="details"),
            ],
        )
        matcher = _make_matcher(schema)
        db_writer = MagicMock(spec=DBWriter)
        
        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup(),
            field_extractor=FieldExtractor()
        )

        # 模擬 Payload：
        # - event_code: 已定義，target_column='event_code'
        # - recipe_id: 已定義，target_column='details'
        # - temp: 未定義 (自動捕捉)
        payload = json.dumps({
            "event_code": "LOAD",
            "recipe_id": "R-101",
            "data": {
                "temp": 250.5
            }
        }).encode()

        pipeline.process(topic, payload)

        # 驗證 DBWriter.add_event 被呼叫
        assert db_writer.add_event.call_count == 1
        record = db_writer.add_event.call_args[0][0]
        
        # 強制印出結果供驗證
        print(f"\n[E2E Verification] Event Code: {record.event_code}")
        print(f"[E2E Verification] Details Bag: {record.details}")
        
        # 1. 實體欄位正確映射
        assert record.event_code == "LOAD"
        
        # 2. 溢位欄位彙整至 details
        assert isinstance(record.details, dict)
        assert record.details["recipe_id"] == "R-101"
        assert record.details["temp"] == 250.5
        
        # 3. 確保 details 中沒有重複的 event_code (因為它已經有專屬 column)
        assert "event_code" not in record.details


class TestPipelineProductionContext:
    """測試 Pipeline 結合生產上下文 (Lot ID) 的邏輯。"""

    def test_telemetry_with_lot_context(self):
        """驗證 Telemetry 寫入時會自動帶上當前的 Lot ID。"""
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)
        
        # Mock Context Cache
        mock_cache = MagicMock()
        # 當查詢 Printer 路徑時，回傳 Lot-999
        mock_cache.get_active_run.return_value = {
            "run_id": 123,
            "lot_id": "LOT-999"
        }

        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup()
        )
        # 注入 Mock Cache
        pipeline._context_cache = mock_cache

        payload = json.dumps({"temperature": 25.0}).encode()
        pipeline.process(topic, payload)

        # 驗證寫入的 Record 包含 Lot ID
        assert db_writer.add_telemetry.call_count == 1
        record = db_writer.add_telemetry.call_args[0][0]
        
        assert record.lot_id == "LOT-999"
        assert record.run_id == 123
        # 驗證快取查詢路徑（應為 asset_path）
        mock_cache.get_active_run.assert_called_once()

class TestPipelineContextData:
    """測試 Pipeline extract_context_data 的邏輯"""

    def test_extract_context_data_telemetry(self):
        topic = "Ent/Site/Area/Line1/Printer/Telemetry"
        matcher = _make_matcher(_telemetry_schema(topic))
        db_writer = MagicMock(spec=DBWriter)
        
        pipeline = Pipeline(
            schema_matcher=matcher,
            db_writer=db_writer,
            tag_lookup=TagLookup()
        )
        
        payload = json.dumps({
            "temperature": 25.0,
            "_meta": {
                "usl": 30.0,
                "lsl": 20.0,
                "target": 25.0,
                "extra_ignored": "ignored"
            }
        }).encode()
        
        pipeline.process(topic, payload)
        
        assert db_writer.add_telemetry.call_count == 1
        record = db_writer.add_telemetry.call_args[0][0]
        
        # Should have captured exactly usl, lsl, target
        assert record.context_data == {
            "usl": 30.0,
            "lsl": 20.0,
            "target": 25.0
        }

