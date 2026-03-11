"""
UNS Consumer 範例：解析 MQTT Topic/Payload，寫入 TimescaleDB

架構設計（參考 OSIsoft PI）：
  - Tag 的「身份」(tag_id) 和「MQTT 來源地址」(mqtt_topic) 分離
  - Consumer 透過 tag_source_mapping 表查找 mqtt_topic → tag_id
  - OT 改 MQTT topic 時，只需更新 mapping，歷史資料不受影響

此範例包含：
  1. TopicParser  — 從 MQTT topic 拆分 asset_path / category / data_point
  2. TagCache     — mapping-based tag 查找 + 自動建立新 tag
  3. TimeSeriesWriter — 依 category 寫入對應的 time-series 表
  4. TagAdmin     — 管理操作：remap（改名）、merge（合併）
  5. MQTT Client  — 訂閱 UNS topic + 主迴圈

依賴套件：
    pip install gmqtt psycopg2-binary

注意：此為參考範例，非 production-ready 程式碼。
"""

import asyncio
import json
import logging
import signal
from datetime import datetime
from typing import Optional

import psycopg2
from gmqtt import Client as MQTTClient
from psycopg2.extras import Json

# =============================================================================
# 設定
# =============================================================================

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_SUBSCRIBE_TOPIC = "uns/#"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "uns_timeseries",
    "user": "uns",
    "password": "uns_password",
}

STANDARD_CATEGORIES = {
    "Telemetry", "Status", "Alarm", "Event", "Command",
    "Config", "Metrics", "Batch", "MasterData", "Maintenance", "Raw",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("uns_consumer")


# =============================================================================
# 1. Topic 解析
# =============================================================================

def parse_topic(topic: str) -> dict:
    """
    從 MQTT topic 中拆分出 asset_path、category、data_point。

    規則：掃描 topic 的每一層，遇到標準 Category 名稱時就是分界線。

    範例：
        'TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature'
        → asset_path = 'TaiwanPrecision/Taoyuan/SMT/Line1/Printer'
        → category   = 'Telemetry'
        → data_point = 'Temperature'
    """
    parts = topic.split("/")

    for i, part in enumerate(parts):
        if part in STANDARD_CATEGORIES:
            asset_path = "/".join(parts[:i])
            category = part
            remaining = parts[i + 1:]
            data_point = "/".join(remaining) if remaining else None
            return {
                "asset_path": asset_path,
                "category": category,
                "data_point": data_point,
            }

    return {
        "asset_path": topic,
        "category": "unknown",
        "data_point": None,
    }


# =============================================================================
# 2. Tag Cache（mapping-based）
# =============================================================================

class TagCache:
    """
    透過 tag_source_mapping 表查找 MQTT topic → tag_id。

    查找流程：
      1. 先查記憶體快取
      2. 快取沒有 → 查 tag_source_mapping 表（active = true）
      3. mapping 也沒有 → 自動建立新 tag + mapping（首次看到的 topic）
    """

    def __init__(self, db_conn):
        self.db = db_conn
        self.cache: dict[str, int] = {}  # mqtt_topic → tag_id
        self._load_active_mappings()

    def _load_active_mappings(self):
        """啟動時載入所有 active 的 mapping"""
        cur = self.db.cursor()
        cur.execute("SELECT mqtt_topic, tag_id FROM tag_source_mapping WHERE active = true")
        for row in cur.fetchall():
            self.cache[row[0]] = row[1]
        cur.close()
        logger.info(f"已載入 {len(self.cache)} 個 active mapping")

    def refresh(self):
        """tag 改名 / remap 後呼叫，重新載入所有 mapping"""
        self.cache.clear()
        self._load_active_mappings()

    def get_tag_id(self, mqtt_topic: str, parsed: dict,
                   unit: Optional[str] = None,
                   data_type: str = "float") -> int:
        """查找或建立 tag_id"""

        # 1. 記憶體快取
        if mqtt_topic in self.cache:
            self._update_last_data(self.cache[mqtt_topic])
            return self.cache[mqtt_topic]

        # 2. 查 DB mapping
        cur = self.db.cursor()
        cur.execute(
            "SELECT tag_id FROM tag_source_mapping WHERE mqtt_topic = %s AND active = true",
            (mqtt_topic,)
        )
        row = cur.fetchone()
        cur.close()

        if row:
            tag_id = row[0]
            self.cache[mqtt_topic] = tag_id
            self._update_last_data(tag_id)
            return tag_id

        # 3. 未知 topic → 自動建立新 tag + mapping
        tag_id = self._create_new_tag(mqtt_topic, parsed, unit, data_type)
        return tag_id

    def _create_new_tag(self, mqtt_topic: str, parsed: dict,
                        unit: Optional[str], data_type: str) -> int:
        """建立新 tag 和對應的 mapping"""
        cur = self.db.cursor()

        # 建 tag
        display_name = parsed.get("data_point") or parsed.get("category", "unknown")
        cur.execute(
            """INSERT INTO tags (display_name, asset_path, category, data_point, unit, data_type)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING tag_id""",
            (display_name, parsed["asset_path"], parsed["category"],
             parsed.get("data_point"), unit, data_type)
        )
        tag_id = cur.fetchone()[0]

        # 建 mapping
        cur.execute(
            """INSERT INTO tag_source_mapping (tag_id, mqtt_topic, mapped_by, notes)
               VALUES (%s, %s, %s, %s)""",
            (tag_id, mqtt_topic, "consumer-auto", "首次收到，自動建立")
        )

        # 記錄變更
        cur.execute(
            """INSERT INTO tag_change_log (tag_id, change_type, new_value, reason, changed_by)
               VALUES (%s, 'create', %s, '新 topic 首次出現', 'consumer-auto')""",
            (tag_id, mqtt_topic)
        )

        self.db.commit()
        cur.close()

        self.cache[mqtt_topic] = tag_id
        logger.info(f"新 tag: {mqtt_topic} → tag_id={tag_id}")
        return tag_id

    def _update_last_data(self, tag_id: int):
        """更新 tag 的最後資料時間"""
        cur = self.db.cursor()
        cur.execute("UPDATE tags SET last_data_at = NOW() WHERE tag_id = %s", (tag_id,))
        self.db.commit()
        cur.close()


# =============================================================================
# 3. Time-Series Writer
# =============================================================================

class TimeSeriesWriter:
    """依 category 將 payload 寫入對應的 time-series 表"""

    def __init__(self, db_conn, tag_cache: TagCache):
        self.db = db_conn
        self.tags = tag_cache

    def write(self, topic: str, payload_bytes: bytes):
        """主入口：解析 topic + payload，寫入對應的表"""

        # 1. 解析 payload（信封格式）
        try:
            msg = json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"無法解析 payload: {topic} → {e}")
            return

        meta = msg.get("_meta", {})
        data = msg.get("data", {})

        # 2. 解析 topic → asset_path / category / data_point
        parsed = parse_topic(topic)

        # 如果 _meta 有 category，優先用
        if "category" in meta:
            parsed["category"] = meta["category"]

        # 3. 取得 timestamp / quality
        timestamp = meta.get("timestamp", datetime.utcnow().isoformat())
        quality = meta.get("quality", "good")

        # 4. 依 category 分流寫入
        #
        # 此 Consumer 只處理 5 種 event-driven category（透過 MQTT 進來的）：
        #   Telemetry, Status, Alarm, Event, Metrics
        #
        # 其餘 4 種 category（Command, Config, Batch, MasterData）走 gRPC，
        # 不經過 MQTT，所以此 Consumer 不需要處理。
        # 詳見 payload_standard_spec.md Part C 的協議選型說明。
        category = parsed["category"]

        try:
            if category == "Telemetry":
                self._write_telemetry(topic, parsed, timestamp, quality, data)
            elif category == "Status":
                self._write_status(topic, parsed, timestamp, data)
            elif category == "Alarm":
                self._write_alarm(topic, parsed, timestamp, data)
            elif category == "Event":
                self._write_event(topic, parsed, timestamp, data)
            elif category == "Metrics":
                self._write_metrics(topic, parsed, timestamp, data)
            else:
                logger.debug(f"跳過非 time-series category: {category} ({topic})")
        except Exception as e:
            logger.error(f"寫入失敗: {topic} → {e}")
            self.db.rollback()

    # --- Telemetry ---

    def _write_telemetry(self, topic, parsed, timestamp, quality, data):
        if "value" in data:
            # 單值
            tag_id = self.tags.get_tag_id(topic, parsed, unit=data.get("unit"))
            cur = self.db.cursor()
            cur.execute(
                "INSERT INTO ts_telemetry (time, tag_id, value, quality) VALUES (%s,%s,%s,%s)",
                (timestamp, tag_id, data["value"], quality)
            )
            self.db.commit()
            cur.close()

        elif "values" in data:
            # 多值：每個 key 拆成獨立的 tag
            units = data.get("units", {})
            for key, value in data["values"].items():
                sub_topic = f"{parsed['asset_path']}/{parsed['category']}/{key}"
                sub_parsed = {**parsed, "data_point": key}
                tag_id = self.tags.get_tag_id(
                    sub_topic, sub_parsed, unit=units.get(key)
                )
                cur = self.db.cursor()
                cur.execute(
                    "INSERT INTO ts_telemetry (time, tag_id, value, quality) VALUES (%s,%s,%s,%s)",
                    (timestamp, tag_id, value, quality)
                )
                self.db.commit()
                cur.close()

    # --- Status ---

    def _write_status(self, topic, parsed, timestamp, data):
        tag_id = self.tags.get_tag_id(topic, parsed, data_type="string")
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO ts_status (time, tag_id, state, sub_state, mode) VALUES (%s,%s,%s,%s,%s)",
            (timestamp, tag_id, data.get("state"), data.get("sub_state"), data.get("mode"))
        )
        self.db.commit()
        cur.close()

    # --- Alarm ---

    def _write_alarm(self, topic, parsed, timestamp, data):
        tag_id = self.tags.get_tag_id(topic, parsed, data_type="json")
        cur = self.db.cursor()
        cur.execute(
            """INSERT INTO ts_alarms (time, tag_id, alarm_id, code, severity, message, state, value, threshold)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (timestamp, tag_id, data.get("alarm_id", ""), data.get("code", ""),
             data.get("severity", "info"), data.get("message"),
             data.get("state", "active"), data.get("current_value"), data.get("threshold"))
        )
        self.db.commit()
        cur.close()

    # --- Event ---

    def _write_event(self, topic, parsed, timestamp, data):
        tag_id = self.tags.get_tag_id(topic, parsed, data_type="json")
        details = {k: v for k, v in data.items() if k not in ("event_id", "event_code", "result")}
        cur = self.db.cursor()
        cur.execute(
            """INSERT INTO ts_events (time, tag_id, event_id, event_code, result, details)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (timestamp, tag_id, data.get("event_id", ""), data.get("event_code", ""),
             data.get("result"), Json(details) if details else None)
        )
        self.db.commit()
        cur.close()

    # --- Metrics ---

    def _write_metrics(self, topic, parsed, timestamp, data):
        tag_id = self.tags.get_tag_id(topic, parsed, data_type="json")
        cur = self.db.cursor()
        cur.execute(
            """INSERT INTO ts_metrics (time, tag_id, metric_type, period, values, context)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (timestamp, tag_id, data.get("metric_type", ""), data.get("period"),
             Json(data.get("values", {})),
             Json(data.get("context")) if data.get("context") else None)
        )
        self.db.commit()
        cur.close()


# =============================================================================
# 4. Tag 管理操作（Admin）
# =============================================================================

class TagAdmin:
    """
    管理員操作：處理 MQTT topic 變更。

    典型場景：
      場景 A（理想）：管理員先執行 remap → OT 再改設備
      場景 B（實務）：OT 先改了設備 → Consumer 自動建新 tag → 管理員事後 merge
    """

    def __init__(self, db_conn, tag_cache: TagCache):
        self.db = db_conn
        self.tag_cache = tag_cache

    def remap_topic(self, old_topic: str, new_topic: str,
                    reason: str = "", changed_by: str = "admin"):
        """
        場景 A：管理員已知 topic 即將改名，先更新 mapping。

        範例：
            admin.remap_topic(
                ".../SMT/Line1/Printer/Telemetry/Temperature",
                ".../SMT/ProductionLine-A/Printer/Telemetry/Temperature",
                reason="產線改名"
            )
        """
        cur = self.db.cursor()

        # 找到舊 mapping 的 tag_id
        cur.execute(
            "SELECT tag_id FROM tag_source_mapping WHERE mqtt_topic = %s AND active = true",
            (old_topic,)
        )
        row = cur.fetchone()
        if not row:
            logger.error(f"找不到 active mapping: {old_topic}")
            cur.close()
            return
        tag_id = row[0]

        # 停用舊 mapping
        cur.execute(
            "UPDATE tag_source_mapping SET active = false WHERE mqtt_topic = %s",
            (old_topic,)
        )

        # 建新 mapping（同一個 tag_id）
        cur.execute(
            """INSERT INTO tag_source_mapping (tag_id, mqtt_topic, mapped_by, notes)
               VALUES (%s, %s, %s, %s)""",
            (tag_id, new_topic, changed_by, reason)
        )

        # 更新 tags 表的 asset_path（可選，讓查詢用新路徑）
        new_parsed = parse_topic(new_topic)
        cur.execute(
            "UPDATE tags SET asset_path = %s WHERE tag_id = %s",
            (new_parsed["asset_path"], tag_id)
        )

        # 記錄變更
        cur.execute(
            """INSERT INTO tag_change_log (tag_id, change_type, old_value, new_value, reason, changed_by)
               VALUES (%s, 'remap', %s, %s, %s, %s)""",
            (tag_id, old_topic, new_topic, reason, changed_by)
        )

        self.db.commit()
        cur.close()

        # 刷新 cache
        self.tag_cache.refresh()
        logger.info(f"Remap 完成: {old_topic} → {new_topic} (tag_id={tag_id})")

    def batch_remap(self, old_prefix: str, new_prefix: str,
                    reason: str = "", changed_by: str = "admin"):
        """
        批次改名：把 old_prefix 開頭的所有 mapping 全部替換為 new_prefix。

        範例（整條產線改名）：
            admin.batch_remap(
                "TaiwanPrecision/Taoyuan/SMT/Line1",
                "TaiwanPrecision/Taoyuan/SMT/ProductionLine-A",
                reason="產線重新命名"
            )
            → 自動處理底下所有 Printer、ReflowOven 等設備的所有 tag
        """
        cur = self.db.cursor()

        # 找出所有受影響的 mapping
        cur.execute(
            "SELECT mapping_id, tag_id, mqtt_topic FROM tag_source_mapping "
            "WHERE mqtt_topic LIKE %s AND active = true",
            (old_prefix + "%",)
        )
        affected = cur.fetchall()
        cur.close()

        if not affected:
            logger.warning(f"找不到 prefix 為 '{old_prefix}' 的 active mapping")
            return

        logger.info(f"批次改名：將影響 {len(affected)} 個 tag")

        for mapping_id, tag_id, old_topic in affected:
            new_topic = old_topic.replace(old_prefix, new_prefix, 1)
            self.remap_topic(old_topic, new_topic, reason=reason, changed_by=changed_by)

        logger.info(f"批次改名完成：{len(affected)} 個 tag 已更新")

    def merge_tags(self, source_tag_id: int, target_tag_id: int,
                   reason: str = "", changed_by: str = "admin"):
        """
        場景 B：OT 先改了 topic → Consumer 自動建了新 tag →
        管理員事後把新 tag (source) 的資料合併到舊 tag (target)。

        範例：
            admin.merge_tags(
                source_tag_id=42,   # Consumer 自動建的新 tag
                target_tag_id=1,    # 原本的 tag（有 3 個月歷史）
                reason="OT 先改了 topic，事後合併"
            )
        """
        cur = self.db.cursor()

        # 把 source 的所有歷史資料改指向 target
        tables = ["ts_telemetry", "ts_status", "ts_alarms", "ts_events", "ts_metrics"]
        total_moved = 0
        for table in tables:
            cur.execute(f"UPDATE {table} SET tag_id = %s WHERE tag_id = %s",
                        (target_tag_id, source_tag_id))
            total_moved += cur.rowcount

        # 把 source 的 mapping 改指向 target
        cur.execute(
            "UPDATE tag_source_mapping SET tag_id = %s WHERE tag_id = %s",
            (target_tag_id, source_tag_id)
        )

        # 記錄變更
        cur.execute(
            """INSERT INTO tag_change_log (tag_id, change_type, old_value, new_value, reason, changed_by)
               VALUES (%s, 'merge', %s, %s, %s, %s)""",
            (target_tag_id, f"source_tag_id={source_tag_id}",
             f"target_tag_id={target_tag_id}", reason, changed_by)
        )

        # 刪除 source tag
        cur.execute("DELETE FROM tags WHERE tag_id = %s", (source_tag_id,))

        self.db.commit()
        cur.close()

        self.tag_cache.refresh()
        logger.info(
            f"Merge 完成: tag_id={source_tag_id} → tag_id={target_tag_id} "
            f"({total_moved} 筆歷史資料已移動)"
        )

    def find_orphan_tags(self, inactive_hours: int = 24) -> list:
        """
        找出超過 N 小時沒有新資料的 tag（可能是 OT 改了 topic，舊 tag 變孤兒）

        用途：定期巡檢，找出需要 merge 或清理的 tag。
        """
        cur = self.db.cursor()
        cur.execute(
            """SELECT t.tag_id, t.display_name, t.asset_path, t.category, t.data_point,
                      t.last_data_at, m.mqtt_topic
               FROM tags t
               JOIN tag_source_mapping m ON t.tag_id = m.tag_id AND m.active = true
               WHERE t.last_data_at < NOW() - INTERVAL '%s hours'
                  OR t.last_data_at IS NULL
               ORDER BY t.last_data_at ASC NULLS FIRST""",
            (inactive_hours,)
        )
        orphans = cur.fetchall()
        cur.close()

        if orphans:
            logger.warning(f"找到 {len(orphans)} 個可能的孤兒 tag：")
            for o in orphans:
                logger.warning(f"  tag_id={o[0]}, {o[2]}/{o[4]}, 最後資料: {o[5]}")

        return orphans


# =============================================================================
# 5. MQTT Client + Main Loop
# =============================================================================

STOP = asyncio.Event()


def on_connect(client, flags, rc, properties):
    logger.info(f"已連線到 MQTT Broker (rc={rc})")
    client.subscribe(MQTT_SUBSCRIBE_TOPIC, qos=1)
    logger.info(f"已訂閱: {MQTT_SUBSCRIBE_TOPIC}")


def on_disconnect(client, packet, exc=None):
    logger.warning("MQTT 連線中斷")


def create_on_message(writer: TimeSeriesWriter):
    def on_message(client, topic, payload, qos, properties):
        writer.write(topic, payload)
    return on_message


async def main():
    # 連接 DB
    logger.info("連接 TimescaleDB...")
    db = psycopg2.connect(**DB_CONFIG)
    tag_cache = TagCache(db)
    writer = TimeSeriesWriter(db, tag_cache)
    admin = TagAdmin(db, tag_cache)

    # 啟動時檢查孤兒 tag
    admin.find_orphan_tags(inactive_hours=24)

    # 連接 MQTT
    client = MQTTClient("uns-consumer-01")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = create_on_message(writer)

    logger.info(f"連接 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}...")
    await client.connect(MQTT_BROKER, MQTT_PORT)

    await STOP.wait()
    await client.disconnect()
    db.close()
    logger.info("Consumer 已關閉")


def ask_exit(*args):
    STOP.set()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, ask_exit)
    loop.add_signal_handler(signal.SIGTERM, ask_exit)
    loop.run_until_complete(main())
