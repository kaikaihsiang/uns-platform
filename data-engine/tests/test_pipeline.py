"""
Tests for UNS Data Engine — Pipeline (end-to-end mock)
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.deadband import DeadbandFilter
from src.db_writer import DBWriter
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
