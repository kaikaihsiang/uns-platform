"""
UNS Data Engine — Schema Matcher

啟動時從 DB 載入 namespace_nodes + schema_types 到記憶體快取。
match(topic) → 回傳 SchemaMatch（包含 persist_mode、fields、timestamp_field 等）。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

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


@dataclass
class SchemaMatch:
    """Schema Matcher 的查詢結果。"""
    node_id: int
    full_path: str
    persist_mode: str           # db / retain / passthrough
    retention_days: int
    schema_type_id: Optional[int] = None
    type_name: Optional[str] = None
    decoder: str = "json"
    timestamp_field: Optional[str] = None
    store_raw: bool = True
    fields: list[FieldDef] = field(default_factory=list)


class SchemaMatcher:
    """
    Topic → SchemaMatch 查詢。

    啟動時從 DB 載入 namespace_nodes + schema_types 到記憶體。
    提供 refresh() 方法給外部觸發重新載入。
    """

    def __init__(self, db_conn=None):
        # topic → SchemaMatch 快取
        self._cache: dict[str, SchemaMatch] = {}
        self._last_refresh = 0.0
        self._db = db_conn
        if db_conn:
            self._load_from_db()

    def _load_from_db(self):
        """從 DB 載入所有 active topic nodes + 對應的 schema_types。"""
        cur = self._db.cursor()
        try:
            cur.execute("""
                SELECT
                    n.node_id, n.full_path, n.persist_mode, n.retention_days,
                    n.schema_type_id,
                    s.type_name, s.decoder, s.timestamp_field, s.store_raw, s.fields
                FROM namespace_nodes n
                LEFT JOIN schema_types s ON n.schema_type_id = s.type_id
                WHERE n.node_type = 'topic'
                  AND n.deleted_at IS NULL
            """)
            rows = cur.fetchall()
        finally:
            cur.close()

        self._cache.clear()
        import time
        self._last_refresh = time.monotonic()

        for row in rows:
            (node_id, full_path, persist_mode, retention_days,
             schema_type_id, type_name, decoder, timestamp_field,
             store_raw, fields_json) = row

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
                    ))

            match = SchemaMatch(
                node_id=node_id,
                full_path=full_path,
                persist_mode=persist_mode or "db",
                retention_days=retention_days or 90,
                schema_type_id=schema_type_id,
                type_name=type_name,
                decoder=decoder or "json",
                timestamp_field=timestamp_field,
                store_raw=bool(store_raw if store_raw is not None else True),
                fields=fields,
            )
            self._cache[full_path] = match

        logger.info("Schema cache loaded: %d topic nodes", len(self._cache))

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
            
        import time
        # Throttled refresh (e.g., at most once every 5 seconds) to discover new topics
        if self._db and (time.monotonic() - self._last_refresh > 5.0):
            self._load_from_db()
            if topic in self._cache:
                return self._cache[topic]

        return None

    def refresh(self):
        """重新載入 DB 快取。"""
        if self._db:
            self._load_from_db()
        else:
            logger.warning("No DB connection, cannot refresh schema cache")
