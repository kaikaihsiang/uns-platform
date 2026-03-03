"""
UNS Data Engine — Pipeline Orchestrator

組裝整條 data pipeline：
  MQTT msg → Decoder → Schema Matcher → Persist Decision
                                         ├── passthrough → skip
                                         ├── retain → skip (PoC)
                                         └── db → Field Extractor → Deadband → DB Writer
                                                └── Raw Writer (if store_raw=true)
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from .config import Config
from .deadband import DeadbandFilter
from .db_writer import DBWriter, RawPayloadRecord, TelemetryRecord
from .decoder import DecodeResult, get_decoder
from .field_extractor import FieldExtractor
from .schema_matcher import SchemaMatcher

logger = logging.getLogger("uns.pipeline")


class TagLookup:
    """
    Tag 查找：MQTT topic + field_name → tag_id。

    啟動時從 DB 載入 tag_source_mapping 到記憶體。
    未知 topic → 自動建立 tag + mapping。
    """

    def __init__(self, db_conn=None):
        self._db = db_conn
        self._cache: dict[str, int] = {}  # "topic::field_name" → tag_id
        if db_conn:
            self._load_from_db()

    def _load_from_db(self):
        """載入所有 active mapping。"""
        cur = self._db.cursor()
        try:
            cur.execute(
                "SELECT mqtt_topic, tag_id FROM tag_source_mapping WHERE active = true"
            )
            for row in cur.fetchall():
                self._cache[row[0]] = row[1]
        finally:
            cur.close()
        logger.info("Tag cache loaded: %d active mappings", len(self._cache))

    def get_tag_id(
        self,
        topic: str,
        field_name: str,
        asset_path: Optional[str] = None,
        unit: Optional[str] = None,
        data_type: str = "float",
    ) -> int:
        """
        查找或建立 tag_id。

        對於有 Schema Type 的 topic，每個 field 是獨立的 tag：
          key = "Enterprise/Site/Line1/Printer/Telemetry::temperature"
        """
        key = f"{topic}::{field_name}" if field_name else topic

        if key in self._cache:
            return self._cache[key]

        if not self._db:
            # 無 DB 連線（測試模式）→ 用 hash 生成 fake tag_id
            fake_id = abs(hash(key)) % 1_000_000
            self._cache[key] = fake_id
            return fake_id

        # 查 DB
        cur = self._db.cursor()
        try:
            # 先查 mapping
            cur.execute(
                "SELECT tag_id FROM tag_source_mapping WHERE mqtt_topic = %s AND active = true",
                (key,),
            )
            row = cur.fetchone()
            if row:
                self._cache[key] = row[0]
                return row[0]

            # 自動建立 tag + mapping
            display_name = field_name or topic.split("/")[-1]
            cur.execute(
                """INSERT INTO tags (display_name, asset_path, category, data_point, unit, data_type)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING tag_id""",
                (
                    display_name,
                    asset_path or topic.rsplit("/", 1)[0] if "/" in topic else topic,
                    "Telemetry",
                    field_name,
                    unit,
                    data_type,
                ),
            )
            tag_id = cur.fetchone()[0]

            cur.execute(
                """INSERT INTO tag_source_mapping (tag_id, mqtt_topic, mapped_by, notes)
                   VALUES (%s, %s, %s, %s)""",
                (tag_id, key, "data-engine-auto", "Auto-created by Data Engine"),
            )

            self._db.commit()
            self._cache[key] = tag_id
            logger.info("New tag created: %s → tag_id=%d", key, tag_id)
            return tag_id

        except Exception as e:
            logger.error("Tag creation failed for %s: %s", key, e)
            self._db.rollback()
            raise
        finally:
            cur.close()

    def refresh(self):
        """重新載入 DB。"""
        if self._db:
            self._cache.clear()
            self._load_from_db()


class Pipeline:
    """
    Data Engine Pipeline — 組裝所有元件。

    使用方式：
        pipeline = Pipeline(db_conn=conn)
        pipeline.process(topic, payload_bytes, receive_time)
    """

    def __init__(
        self,
        db_conn=None,
        schema_matcher: Optional[SchemaMatcher] = None,
        tag_lookup: Optional[TagLookup] = None,
        db_writer: Optional[DBWriter] = None,
        deadband_filter: Optional[DeadbandFilter] = None,
        field_extractor: Optional[FieldExtractor] = None,
        bootstrap_until: Optional[datetime] = None,
    ):
        self._schema_matcher = schema_matcher or SchemaMatcher(db_conn)
        self._tag_lookup = tag_lookup or TagLookup(db_conn)
        self._db_writer = db_writer or (DBWriter(
            db_conn,
            batch_size=Config.BATCH_SIZE,
            batch_interval_sec=Config.BATCH_INTERVAL_SEC,
        ) if db_conn else None)
        self._deadband = deadband_filter or DeadbandFilter(
            enabled=Config.DEADBAND_ENABLED
        )
        self._extractor = field_extractor or FieldExtractor()
        self._bootstrap_until = bootstrap_until

        # 統計
        self._total_processed = 0
        self._total_skipped = 0
        self._total_passthrough = 0
        self._total_no_schema = 0

    def process(
        self,
        topic: str,
        payload_bytes: bytes,
        receive_time: Optional[datetime] = None,
    ):
        """
        處理一筆 MQTT 訊息。

        Args:
            topic: MQTT topic
            payload_bytes: raw payload bytes
            receive_time: 收到訊息的時間
        """
        if receive_time is None:
            receive_time = datetime.now(timezone.utc)

        self._total_processed += 1

        # Bootstrap mode：啟動期間不寫 DB（避免 retained message 重複寫）
        if self._bootstrap_until and receive_time < self._bootstrap_until:
            logger.debug("Bootstrap mode, skipping: %s", topic)
            self._total_skipped += 1
            return

        # 1. Schema Matcher
        schema = self._schema_matcher.match(topic)
        if schema is None:
            # 未註冊的 topic → 跳過（Phase 1 不做 auto-detect 寫入）
            self._total_no_schema += 1
            logger.debug("No schema for topic: %s", topic)
            return

        # 2. Persist Decision
        if schema.persist_mode == "passthrough":
            self._total_passthrough += 1
            return

        if schema.persist_mode == "retain":
            # PoC 階段不主動管 EMQX retain，只跳過 DB 寫入
            self._total_passthrough += 1
            return

        # 3. Decode
        decoder = get_decoder(schema.decoder)
        result: DecodeResult = decoder.decode(payload_bytes)
        if not result.ok:
            logger.warning("Decode failed for %s: %s", topic, result.error)
            return

        payload = result.data

        # 4. Raw Storage（Dual Storage）
        if schema.store_raw and self._db_writer:
            payload_size = len(payload_bytes) if payload_bytes else 0
            self._db_writer.add_raw_payload(RawPayloadRecord(
                time=receive_time,
                topic=topic,
                payload=payload,
                schema_type_id=schema.schema_type_id,
                payload_size=payload_size,
            ))

        # 5. Field Extraction
        if not schema.fields:
            # 沒有 fields 定義 → 只存 raw
            return

        extracted_values = self._extractor.extract(payload, schema, receive_time)

        # 6. Deadband + Write
        for ev in extracted_values:
            if not ev.persist:
                continue

            tag_id = self._tag_lookup.get_tag_id(
                topic=topic,
                field_name=ev.tag_suffix,
                unit=ev.unit,
                data_type=ev.field_type,
            )

            # Deadband check
            check_value = ev.value if ev.value is not None else ev.value_text
            if not self._deadband.should_write(tag_id, check_value, ev.deadband):
                self._total_skipped += 1
                continue

            if self._db_writer:
                self._db_writer.add_telemetry(TelemetryRecord(
                    time=ev.timestamp,
                    tag_id=tag_id,
                    value=ev.value,
                    value_text=ev.value_text,
                    value_json=ev.value_json,
                    quality="good",
                ))

    def flush(self):
        """強制 flush DB writer buffer。"""
        if self._db_writer:
            self._db_writer.flush()

    def close(self):
        """Graceful shutdown。"""
        if self._db_writer:
            self._db_writer.close()

    @property
    def stats(self) -> dict:
        """Pipeline 統計。"""
        result = {
            "total_processed": self._total_processed,
            "total_skipped": self._total_skipped,
            "total_passthrough": self._total_passthrough,
            "total_no_schema": self._total_no_schema,
            "deadband_tracked_tags": self._deadband.state_count,
        }
        if self._db_writer:
            result["db_writer"] = self._db_writer.stats
        return result
