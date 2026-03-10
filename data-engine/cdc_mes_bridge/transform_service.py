"""
CDC Transform Service：MES PostgreSQL Change Event → UNS MQTT Payload

此服務從 Kafka 消費 Debezium 產生的 Change Event，
將 MES DB 的 row 變更轉換成 UNS 信封格式，發佈到 MQTT Broker。

MES 工程師不需要改任何程式碼。

架構位置：
  MES PostgreSQL → Debezium → Kafka → [此服務] → MQTT Broker → UNS Consumer → TimescaleDB

依賴：
    pip install confluent-kafka paho-mqtt

使用：
    python transform_service.py
"""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from confluent_kafka import Consumer as KafkaConsumer
import paho.mqtt.client as mqtt

# =============================================================================
# 設定
# =============================================================================

KAFKA_CONFIG = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "uns-cdc-transform",
    "auto.offset.reset": "earliest",
}

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Debezium 產生的 Kafka topic 命名規則：
# {topic.prefix}.{schema}.{table}
KAFKA_TOPICS = [
    "mes.public.event_tracking",
    "mes.public.lot",
    "mes.public.equipment",
]

# UNS 的 Enterprise/Site 前綴（部署時設定）
UNS_PREFIX = "TaiwanPrecision/Taoyuan"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cdc_transform")


# =============================================================================
# Transform Rules
# =============================================================================
# 每個客戶的 MES DB schema 不同，所以 transform rules 要客製化。
# 以下是針對 mes_sample_schema.sql 的規則。
# 導入新客戶時，只需要修改這個 section。
# =============================================================================

class TransformRules:
    """
    將 Debezium Change Event 轉換成 UNS MQTT 信封格式。

    每個 handler 方法對應一張 MES 表。
    回傳 (topic, payload, retain) tuple，或 None 表示忽略此事件。
    """

    def __init__(self, uns_prefix: str):
        self.prefix = uns_prefix

    def transform(self, table: str, operation: str, before: dict, after: dict):
        """
        主入口：根據表名分派到對應的 handler。

        Args:
            table: 表名（如 'event_tracking'）
            operation: 操作類型 ('c'=insert, 'u'=update, 'd'=delete, 'r'=snapshot)
            before: 變更前的 row（UPDATE/DELETE 才有）
            after: 變更後的 row（INSERT/UPDATE 才有）
        """
        handler = {
            "event_tracking": self._handle_event_tracking,
            "lot": self._handle_lot,
            "equipment": self._handle_equipment,
        }.get(table)

        if handler:
            return handler(operation, before, after)
        return None

    # ─── event_tracking 表：INSERT → UNS Event ───

    def _handle_event_tracking(self, op, before, after):
        """
        MES event_tracking 表的每筆 INSERT → 發到 UNS Event topic。

        例：LotMoveIn 時，MES 寫了一筆 event_tracking，
            Debezium 捕捉到 INSERT，我們轉成 UNS Event 信封格式。
        """
        if op not in ("c", "r"):  # 只處理 INSERT 和 snapshot
            return None

        row = after
        if not row:
            return None

        # 組 MQTT topic
        area = row.get("area_id", "unknown")
        line = row.get("line_id", "unknown")
        equipment = row.get("equipment_id", "unknown")
        event_code = row.get("event_code", "unknown")

        topic = f"{self.prefix}/{area}/{line}/{equipment}/Event/{event_code}"

        # 組 UNS 信封 payload
        payload = {
            "_meta": {
                "category": "Event",
                "schema_version": "1.0",
                "source": f"MES/CDC/{row.get('equipment_id', 'unknown')}",
                "timestamp": self._to_iso(row.get("created_at")),
                "quality": "good",
            },
            "data": {
                "event_code": event_code,
                "event_id": f"CDC-{row.get('event_id', uuid4())}",
                "lot_id": row.get("lot_id"),
                "equipment_id": row.get("equipment_id"),
                "operator_id": row.get("operator_id"),
                "result": row.get("result"),
                "details": row.get("details"),
            }
        }

        return (topic, payload, False)  # Event 不 retain

    # ─── equipment 表：state UPDATE → UNS Status ───

    def _handle_equipment(self, op, before, after):
        """
        equipment 表的 state 欄位 UPDATE → 發到 UNS Status topic。

        例：LotMoveIn 後設備 state 從 'idle' 變成 'running'。
        """
        if op not in ("u", "r"):  # 只處理 UPDATE 和 snapshot
            return None

        row = after
        if not row:
            return None

        # 如果是 UPDATE，檢查 state 是否有變
        if op == "u" and before:
            if before.get("state") == row.get("state") and before.get("mode") == row.get("mode"):
                return None  # state 沒變，不發

        area = row.get("area_id", "unknown")
        line = row.get("line_id", "unknown")
        equipment = row.get("equipment_id", "unknown")

        topic = f"{self.prefix}/{area}/{line}/{equipment}/Status/MachineState"

        payload = {
            "_meta": {
                "category": "Status",
                "schema_version": "1.0",
                "source": f"MES/CDC/{equipment}",
                "timestamp": self._to_iso(row.get("updated_at")),
                "quality": "good",
            },
            "data": {
                "state": row.get("state", "unknown"),
                "mode": row.get("mode"),
                "current_lot": row.get("current_lot"),
            }
        }

        return (topic, payload, True)  # Status 要 retain！

    # ─── lot 表：state UPDATE → UNS Status ───

    def _handle_lot(self, op, before, after):
        """
        lot 表的 state UPDATE → 發到 UNS Event topic。

        例：lot state 從 'queued' 變成 'in_process'。
        """
        if op not in ("u", "r"):
            return None

        row = after
        if not row:
            return None

        # 只在 state 變化時觸發
        if op == "u" and before:
            if before.get("state") == row.get("state"):
                return None

        line = row.get("line_id", "unknown")
        equipment = row.get("equipment_id", "unknown")

        topic = f"{self.prefix}/SMT/{line}/{equipment}/Event/LotStateChange"

        payload = {
            "_meta": {
                "category": "Event",
                "schema_version": "1.0",
                "source": f"MES/CDC/{equipment}",
                "timestamp": self._to_iso(row.get("updated_at")),
                "quality": "good",
            },
            "data": {
                "event_code": "lot_state_change",
                "event_id": f"CDC-LOT-{uuid4()}",
                "lot_id": row.get("lot_id"),
                "new_state": row.get("state"),
                "old_state": before.get("state") if before else None,
                "equipment_id": equipment,
                "good_qty": row.get("good_qty"),
                "ng_qty": row.get("ng_qty"),
            }
        }

        return (topic, payload, False)

    # ─── 工具方法 ───

    @staticmethod
    def _to_iso(value):
        """將 Debezium 的 timestamp 轉成 ISO 8601"""
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(value, (int, float)):
            # Debezium 用 epoch microseconds
            return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc).isoformat()
        if isinstance(value, str):
            return value
        return str(value)


# =============================================================================
# Debezium Change Event 解析
# =============================================================================

def parse_debezium_event(raw_value: bytes) -> dict:
    """
    解析 Debezium 產生的 Change Event JSON。

    Debezium Change Event 格式：
    {
        "schema": { ... },
        "payload": {
            "before": { ... } or null,
            "after": { ... } or null,
            "source": { "table": "event_tracking", ... },
            "op": "c" / "u" / "d" / "r",
            "ts_ms": 1705305600000
        }
    }
    """
    event = json.loads(raw_value.decode("utf-8"))

    # Debezium 的 payload 可能在頂層或巢套在 "payload" 裡
    payload = event.get("payload", event)

    return {
        "table": payload.get("source", {}).get("table", "unknown"),
        "operation": payload.get("op", "?"),
        "before": payload.get("before"),
        "after": payload.get("after"),
        "ts_ms": payload.get("ts_ms"),
    }


# =============================================================================
# 主程式
# =============================================================================

def main():
    # 初始化 Transform Rules
    rules = TransformRules(uns_prefix=UNS_PREFIX)

    # 初始化 Kafka Consumer
    kafka = KafkaConsumer(KAFKA_CONFIG)
    kafka.subscribe(KAFKA_TOPICS)
    logger.info(f"Kafka Consumer 已訂閱: {KAFKA_TOPICS}")

    # 初始化 MQTT Client
    mqtt_client = mqtt.Client(client_id="cdc-transform-01")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()
    logger.info(f"MQTT 已連線: {MQTT_BROKER}:{MQTT_PORT}")

    # 統計
    stats = {"total": 0, "published": 0, "skipped": 0, "errors": 0}

    try:
        while True:
            msg = kafka.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Kafka error: {msg.error()}")
                stats["errors"] += 1
                continue

            stats["total"] += 1

            try:
                # 1. 解析 Debezium Change Event
                event = parse_debezium_event(msg.value())

                # 2. 轉換成 UNS 格式
                result = rules.transform(
                    table=event["table"],
                    operation=event["operation"],
                    before=event["before"],
                    after=event["after"],
                )

                if result is None:
                    stats["skipped"] += 1
                    continue

                topic, payload, retain = result

                # 3. 發佈到 MQTT
                mqtt_client.publish(
                    topic=topic,
                    payload=json.dumps(payload, ensure_ascii=False),
                    qos=1,
                    retain=retain,
                )

                stats["published"] += 1
                logger.info(
                    f"[{event['table']}.{event['operation']}] → {topic} "
                    f"(published: {stats['published']}/{stats['total']})"
                )

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Transform 失敗: {e}", exc_info=True)

    except KeyboardInterrupt:
        logger.info("收到中斷訊號，關閉中...")
    finally:
        kafka.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info(
            f"統計: total={stats['total']}, published={stats['published']}, "
            f"skipped={stats['skipped']}, errors={stats['errors']}"
        )


if __name__ == "__main__":
    main()
