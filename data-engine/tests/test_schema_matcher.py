"""
Tests for UNS Data Engine — Schema Matcher
"""

from src.schema_matcher import SchemaMatcher, SchemaMatch, FieldDef


class TestSchemaMatcher:
    """Schema Matcher 測試（純記憶體，不需 DB）。"""

    def setup_method(self):
        self.matcher = SchemaMatcher()
        # 載入測試資料
        self.matcher.load_from_data([
            SchemaMatch(
                node_id=1,
                full_path="TestEnt/TestSite/Area1/Line1/Printer/Telemetry",
                persist_mode="db",
                retention_days=90,
                schema_type_id=1,
                type_name="SMT_Printer_Telemetry",
                decoder="json",
                timestamp_field="$._meta.timestamp",
                store_raw=True,
                fields=[
                    FieldDef(name="temperature", path="$.temperature", type="float",
                             unit="°C", deadband=0.1),
                    FieldDef(name="pressure", path="$.pressure", type="float",
                             unit="kPa", deadband=0.05),
                ],
            ),
            SchemaMatch(
                node_id=2,
                full_path="TestEnt/TestSite/Area1/Line1/Printer/Status",
                persist_mode="retain",
                retention_days=30,
                schema_type_id=2,
                type_name="Equipment_Status",
                decoder="json",
                store_raw=False,
            ),
            SchemaMatch(
                node_id=3,
                full_path="TestEnt/TestSite/Area1/Line1/Printer/Heartbeat",
                persist_mode="passthrough",
                retention_days=0,
            ),
        ])

    def test_match_found(self):
        """已註冊的 topic 可以找到。"""
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Telemetry")
        assert result is not None
        assert result.node_id == 1
        assert result.type_name == "SMT_Printer_Telemetry"
        assert result.persist_mode == "db"
        assert len(result.fields) == 2

    def test_match_not_found(self):
        """未註冊的 topic → None。"""
        result = self.matcher.match("Unknown/Topic/Path")
        assert result is None

    def test_persist_mode_db(self):
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Telemetry")
        assert result.persist_mode == "db"

    def test_persist_mode_retain(self):
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Status")
        assert result.persist_mode == "retain"

    def test_persist_mode_passthrough(self):
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Heartbeat")
        assert result.persist_mode == "passthrough"

    def test_fields_populated(self):
        """fields 正確載入。"""
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Telemetry")
        assert len(result.fields) == 2
        temp_field = result.fields[0]
        assert temp_field.name == "temperature"
        assert temp_field.path == "$.temperature"
        assert temp_field.type == "float"
        assert temp_field.unit == "°C"
        assert temp_field.deadband == 0.1

    def test_store_raw_flag(self):
        """store_raw 正確回傳。"""
        result_telem = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Telemetry")
        assert result_telem.store_raw is True

        result_status = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Status")
        assert result_status.store_raw is False

    def test_miss_cache(self):
        """未命中的 topic 會被快取，第二次不再查。"""
        r1 = self.matcher.match("Some/Unknown/Topic")
        assert r1 is None
        # 第二次應該直接返回 None（從 miss cache）
        r2 = self.matcher.match("Some/Unknown/Topic")
        assert r2 is None

    def test_decoder_type(self):
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Telemetry")
        assert result.decoder == "json"

    def test_timestamp_field(self):
        result = self.matcher.match("TestEnt/TestSite/Area1/Line1/Printer/Telemetry")
        assert result.timestamp_field == "$._meta.timestamp"
