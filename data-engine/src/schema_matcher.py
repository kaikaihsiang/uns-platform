"""
UNS Data Engine — Schema Matcher

啟動時從 DB 載入 namespace_nodes + schema_types 到記憶體快取。
match(topic) → 回傳 SchemaMatch（包含 persist_mode、fields、timestamp_field 等）。
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import psycopg2
from .db_pool import DBPool

logger = logging.getLogger("uns.schema_matcher")


@dataclass
class FieldDef:
    """Schema Type 中的單一欄位定義。"""
    name: str
    path: str              # JSONPath，如 '$.temperature'
    type: str = "float"    # float / integer / string / boolean / json
    unit: Optional[str] = None
    extract: bool = True
    persist: bool = True
    deadband: object = None   # None / float / "change_only"
    array_mode: str = "single"  # single / expand / avg / last
    target_column: Optional[str] = None


@dataclass
class SchemaMatch:
    """Schema Matcher 的查詢結果。"""
    node_id: int
    full_path: str
    persist_mode: str           # db / retain / passthrough
    retention_days: int
    schema_id: Optional[int] = None
    schema_name: Optional[str] = None
    decoder: str = "json"
    timestamp_field: Optional[str] = None
    store_raw: bool = True
    schema_category: str = "telemetry"
    fields: list[FieldDef] = field(default_factory=list)


class SchemaMatcher:
    """
    Topic → SchemaMatch 查詢。

    啟動時從 DB 載入 namespace_nodes + schema_types 到記憶體。
    提供 refresh() 方法給外部觸發重新載入。
    """

    def __init__(self, db_pool: Optional[DBPool] = None):
        # topic → SchemaMatch 快取
        self._cache: dict[str, SchemaMatch] = {}
        self._last_refresh = 0.0
        self._db_pool = db_pool
        if db_pool:
            self._load_from_db()

    def _load_from_db(self):
        """從 DB 載入所有 active topic nodes + 對應的 schema_types。"""
        if not self._db_pool:
            return

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT
                        n.node_id, n.full_path, n.persist_mode, n.retention_days,
                        n.schema_id,
                        s.schema_name, s.decoder, s.timestamp_field, s.store_raw, s.fields,
                        s.schema_category
                    FROM namespace_nodes n
                    LEFT JOIN uns_payload_schemas s ON n.schema_id = s.schema_id
                    WHERE n.node_type = 'topic'
                      AND n.deleted_at IS NULL
                """)
                rows = cur.fetchall()
                cur.close()

            self._cache.clear()
            self._last_refresh = time.monotonic()

            for row in rows:
                (node_id, full_path, persist_mode, retention_days,
                 schema_id, schema_name, decoder, timestamp_field,
                 store_raw, fields_json, schema_category) = row

                fields = []
                if fields_json:
                    for f in fields_json:
                        fields.append(FieldDef(
                            name=f.get("name", ""),
                            path=f.get("path", f"$.{f.get('name', '')}"),
                            type=f.get("type", "float"),
                            unit=f.get("unit"),
                            extract=f.get("extract", True),
                            persist=f.get("persist", True),
                            deadband=f.get("deadband"),
                            array_mode=f.get("array_mode", "single"),
                            target_column=f.get("target_column"),
                        ))

                match = SchemaMatch(
                    node_id=node_id,
                    full_path=full_path,
                    persist_mode=persist_mode or "db",
                    retention_days=retention_days or 90,
                    schema_id=schema_id,
                    schema_name=schema_name,
                    decoder=decoder or "json",
                    timestamp_field=timestamp_field,
                    store_raw=bool(store_raw if store_raw is not None else True),
                    schema_category=schema_category or "telemetry",
                    fields=fields,
                )
                self._cache[full_path] = match

            logger.info("Schema cache loaded: %d topic nodes", len(self._cache))
        except Exception as e:
            logger.error(f"Failed to load schema cache: {e}")

    def load_from_data(self, matches: list[SchemaMatch]):
        """
        從記憶體資料載入（用於測試或無 DB 場景）。
        """
        self._cache.clear()
        for m in matches:
            self._cache[m.full_path] = m

    def match(self, topic: str) -> Optional[SchemaMatch]:
        """
        查詢 topic 對應的 SchemaMatch。

        Returns:
            SchemaMatch if topic is a registered topic node, else None.
        """
        if topic in self._cache:
            return self._cache[topic]
            
        # Throttled refresh (e.g., at most once every 5 seconds) to discover new topics
        if self._db_pool and (time.monotonic() - self._last_refresh > 5.0):
            self._load_from_db()
            if topic in self._cache:
                return self._cache[topic]

        return None

    def refresh(self):
        """重新載入 DB 快取。"""
        if self._db_pool:
            self._load_from_db()
        else:
            logger.warning("No DB pool, cannot refresh schema cache")
