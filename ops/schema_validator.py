"""
schema_validator.py — UNS Schema 驗證器

輕量級的 Schema-on-Read 驗證器，搭配 schema_registry 表使用。
可直接 import 到 consumer_example.py。

功能：
  1. 從 schema_registry 表載入已註冊的 JSON Schema
  2. 驗證 MQTT payload 是否符合 schema
  3. 首次遇到新 topic 時，用 genson 自動推斷 schema 並寫入 registry
  4. 偵測 breaking changes（欄位刪除、型別改變、新增必填欄位）
  5. 三種模式：off / log / strict

用法：
    from schema_validator import SchemaValidator

    validator = SchemaValidator(db_conn, mode="log")

    # 在 Consumer 的 on_message 中
    is_valid = validator.validate(
        topic="TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature",
        version="1.0",
        payload={"value": 25.3, "unit": "°C"}
    )

    # 比較兩個版本的 schema
    changes = SchemaValidator.detect_breaking_changes(old_schema, new_schema)

依賴套件：
    pip install psycopg2-binary jsonschema genson
"""

import logging
from typing import Optional

from psycopg2.extras import Json

logger = logging.getLogger("uns_consumer.schema")


class SchemaValidator:
    """
    輕量級 Schema 驗證器。

    三種模式：
      - "off"    — 不驗證，不記錄（Phase 0）
      - "log"    — 驗證失敗時記 warning，不丟棄訊息（Phase 2）
      - "strict" — 驗證失敗時丟棄訊息 + 發送告警（Phase 3）
    """

    def __init__(self, db_conn, mode: str = "log", metrics=None):
        """
        Args:
            db_conn: psycopg2 連線
            mode: "off" / "log" / "strict"
            metrics: ConsumerMetrics 實例（可選，用於記錄 Prometheus 指標）
        """
        if mode not in ("off", "log", "strict"):
            raise ValueError(f"無效的 mode: {mode}，必須是 off / log / strict")

        self.db = db_conn
        self.mode = mode
        self.metrics = metrics
        self.cache: dict[str, dict] = {}   # "topic:version" → json_schema
        self._load_schemas()

    def _load_schemas(self):
        """啟動時載入所有已註冊的 schema 到記憶體快取"""
        cur = self.db.cursor()
        cur.execute(
            "SELECT topic_pattern, schema_version, json_schema "
            "FROM schema_registry ORDER BY registered_at DESC"
        )
        for row in cur.fetchall():
            topic_pattern, version, schema = row
            key = f"{topic_pattern}:{version}"
            self.cache[key] = schema
        cur.close()
        logger.info(f"已載入 {len(self.cache)} 個 schema")

    def refresh(self):
        """強制重新載入所有 schema"""
        self.cache.clear()
        self._load_schemas()

    def validate(self, topic: str, version: str, payload: dict) -> bool:
        """
        驗證 payload 是否符合註冊的 schema。

        Args:
            topic: MQTT topic
            version: payload 的 schema_version（來自 _meta.schema_version）
            payload: payload 的 data 部分

        Returns:
            True = 通過或不需驗證，False = strict 模式下驗證失敗
        """
        if self.mode == "off":
            if self.metrics:
                self.metrics.schema_validations.labels(result="skipped").inc()
            return True

        key = f"{topic}:{version}"
        schema = self.cache.get(key)

        if schema is None:
            # 未知的 schema → 自動推斷並註冊
            self._auto_register(topic, version, payload)
            if self.metrics:
                self.metrics.schema_validations.labels(result="pass").inc()
            return True

        # 驗證
        try:
            import jsonschema
            jsonschema.validate(payload, schema)

            if self.metrics:
                self.metrics.schema_validations.labels(result="pass").inc()
            return True

        except jsonschema.ValidationError as e:
            if self.metrics:
                self.metrics.schema_validations.labels(result="fail").inc()
                self.metrics.schema_validation_failures.labels(
                    topic_pattern=topic
                ).inc()

            if self.mode == "strict":
                logger.error(
                    f"Schema 驗證失敗（丟棄）: {topic} v{version} → {e.message}"
                )
                return False
            else:
                logger.warning(
                    f"Schema 驗證失敗（記錄）: {topic} v{version} → {e.message}"
                )
                return True   # log 模式不丟棄

    def _auto_register(self, topic: str, version: str, payload: dict):
        """首次遇到新 topic 時，自動推斷 schema 並寫入 registry"""
        try:
            from genson import SchemaBuilder

            builder = SchemaBuilder()
            builder.add_object(payload)
            inferred_schema = builder.to_schema()

            cur = self.db.cursor()

            # 查看是否已有更早的版本（偵測 breaking change）
            cur.execute(
                "SELECT schema_version, json_schema FROM schema_registry "
                "WHERE topic_pattern = %s "
                "ORDER BY registered_at DESC LIMIT 1",
                (topic,)
            )
            prev = cur.fetchone()

            is_compatible = True
            breaking_desc = None

            if prev:
                prev_version, prev_schema = prev
                changes = self.detect_breaking_changes(prev_schema, inferred_schema)
                if changes:
                    is_compatible = False
                    breaking_desc = "; ".join(changes)
                    logger.warning(
                        f"Schema breaking change: {topic} "
                        f"v{prev_version} → v{version}: {breaking_desc}"
                    )

            # 寫入 registry
            cur.execute(
                """INSERT INTO schema_registry
                   (topic_pattern, category, schema_version, json_schema,
                    is_compatible, breaking_changes, registered_by, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (topic_pattern, schema_version) DO NOTHING""",
                (topic, self._extract_category(topic), version,
                 Json(inferred_schema), is_compatible, breaking_desc,
                 "consumer-auto", "自動推斷")
            )

            # 寫入 change log
            cur.execute(
                """INSERT INTO schema_change_log
                   (topic_pattern, old_version, new_version, change_type,
                    is_compatible, breaking_changes, changed_by, reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (topic, prev[0] if prev else None, version, "register",
                 is_compatible, breaking_desc,
                 "consumer-auto", "首次收到，自動推斷")
            )

            self.db.commit()
            cur.close()

            self.cache[f"{topic}:{version}"] = inferred_schema
            logger.info(f"自動註冊 schema: {topic} v{version}")

        except ImportError:
            logger.warning("genson 未安裝，無法自動推斷 schema")
        except Exception as e:
            logger.error(f"自動註冊 schema 失敗: {topic} → {e}")
            self.db.rollback()

    @staticmethod
    def _extract_category(topic: str) -> str:
        """從 topic 中提取 category"""
        standard = {
            "Telemetry", "Status", "Alarm", "Event", "Command",
            "Config", "Metrics", "Batch", "MasterData", "Maintenance",
        }
        for part in topic.split("/"):
            if part in standard:
                return part
        return "unknown"

    @staticmethod
    def detect_breaking_changes(
        old_schema: dict, new_schema: dict
    ) -> list[str]:
        """
        比較兩個 JSON Schema，找出不相容的變更。

        回傳 breaking change 描述列表。空列表 = 相容。

        偵測範圍：
          - 欄位被刪除
          - 新增必填欄位
          - 欄位型別改變
          - 必填欄位變更
        """
        changes = []

        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))

        # 1. 刪除的欄位
        for prop in old_props:
            if prop not in new_props:
                changes.append(f"欄位 '{prop}' 被刪除")

        # 2. 新增的必填欄位（舊版沒有）
        for prop in new_required - old_required:
            if prop not in old_props:
                changes.append(f"新增必填欄位 '{prop}'")

        # 3. 型別改變
        for prop in old_props:
            if prop in new_props:
                old_type = old_props[prop].get("type")
                new_type = new_props[prop].get("type")
                if old_type and new_type and old_type != new_type:
                    changes.append(
                        f"欄位 '{prop}' 型別從 '{old_type}' 改為 '{new_type}'"
                    )

        # 4. 原本選填變必填
        for prop in new_required:
            if prop in old_props and prop not in old_required:
                changes.append(f"欄位 '{prop}' 從選填變為必填")

        return changes

    def get_latest_schema(self, topic: str) -> Optional[dict]:
        """取得某 topic 的最新版 schema"""
        cur = self.db.cursor()
        cur.execute(
            "SELECT json_schema FROM schema_registry "
            "WHERE topic_pattern = %s "
            "ORDER BY registered_at DESC LIMIT 1",
            (topic,)
        )
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def list_schemas(self, category: Optional[str] = None) -> list[dict]:
        """列出所有已註冊的 schema（可依 category 過濾）"""
        cur = self.db.cursor()
        if category:
            cur.execute(
                "SELECT topic_pattern, schema_version, category, "
                "is_compatible, registered_at, registered_by "
                "FROM schema_registry WHERE category = %s "
                "ORDER BY topic_pattern, registered_at DESC",
                (category,)
            )
        else:
            cur.execute(
                "SELECT topic_pattern, schema_version, category, "
                "is_compatible, registered_at, registered_by "
                "FROM schema_registry "
                "ORDER BY topic_pattern, registered_at DESC"
            )
        rows = cur.fetchall()
        cur.close()

        return [
            {
                "topic_pattern": r[0],
                "schema_version": r[1],
                "category": r[2],
                "is_compatible": r[3],
                "registered_at": r[4].isoformat() if r[4] else None,
                "registered_by": r[5],
            }
            for r in rows
        ]
