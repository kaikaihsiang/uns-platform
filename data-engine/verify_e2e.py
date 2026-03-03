"""
UNS Data Engine - E2E Verification Script
這個腳本設計用來驗證 poc_feature_scope.md 中定義的四個主要 Data Engine 驗收標準：
1. 30秒寫入測試 (Schema 綁定與正常寫入)
2. Deadband 測試 (重複數值過濾)
3. Raw 存儲 (Dual Storage 行為)
4. (斷線重連請以 Docker 重啟手動測試，此腳本不含此項)
"""

import time
import json
import logging
import psycopg2
import paho.mqtt.publish as publish
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e_verify")

def execute_query(query, params=None, fetch=True):
    conn = psycopg2.connect(**Config.db_dsn())
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        res = cur.fetchall() if fetch else None
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query}")
        res = None
    finally:
        cur.close()
        conn.close()
    return res

def setup_test_schema_and_node():
    logger.info("Setting up Test Schema and Namespace Node...")
    # 確保資料表乾淨 (只刪除測試用的 node)
    execute_query("DELETE FROM namespace_nodes WHERE full_path = 'Test/E2E/Machine'; ", fetch=False)
    execute_query("DELETE FROM schema_types WHERE type_name = 'E2ESchema'; ", fetch=False)

    # 1. 建立 Schema
    fields = json.dumps([
        {"name": "temperature", "path": "$.temperature", "type": "float", "deadband": 0.5},
        {"name": "pressure", "path": "$.pressure", "type": "float"}
    ])
    res = execute_query(
        "INSERT INTO schema_types (type_name, decoder, store_raw, fields) VALUES (%s, %s, %s, %s) RETURNING type_id",
        ('E2ESchema', 'json', True, fields)
    )
    schema_id = res[0][0]

    # 2. 建立 Node
    execute_query(
        "INSERT INTO namespace_nodes (name, node_type, full_path, schema_type_id, persist_mode) VALUES (%s, %s, %s, %s, %s)",
        ('Machine', 'topic', 'Test/E2E/Machine', schema_id, 'db'),
        fetch=False
    )
    logger.info("Test Schema and Node created successfully. Waiting 6s for Data Engine to refresh its cache...")
    time.sleep(6)

def verify():
    test_topic = "Test/E2E/Machine"
    
    logger.info("=== Starting E2E Verification ===")
    setup_test_schema_and_node()
    
    # 清空測試用的舊資料
    logger.info("Cleaning up old telemetry/raw payloads for the test topic...")
    execute_query("DELETE FROM ts_raw_payloads WHERE mqtt_topic = %s", (test_topic,), fetch=False)
    
    # 清理 tags 與 ts_telemetry
    asset_path = "Test/E2E"
    tags_to_delete = execute_query("SELECT tag_id FROM tags WHERE asset_path = %s", (asset_path,))
    if tags_to_delete:
        tag_ids = tuple([t[0] for t in tags_to_delete])
        execute_query("DELETE FROM ts_telemetry WHERE tag_id IN %s", (tag_ids,), fetch=False)
        execute_query("DELETE FROM tag_source_mapping WHERE tag_id IN %s", (tag_ids,), fetch=False)
        execute_query("DELETE FROM tags WHERE tag_id IN %s", (tag_ids,), fetch=False)
    
    # ----- 測試 1 & 3: 正常寫入與 Raw 存儲 -----
    logger.info("\n[Test 1 & 3] Normal Write & Raw Storage")
    payload_1 = {"temperature": 25.3, "pressure": 2.1}
    logger.info(f"Publishing to EMQX ({test_topic}): {payload_1}")
    publish.single(test_topic, json.dumps(payload_1), hostname="localhost")
    
    time.sleep(2) # 等待 Data Engine 批次寫入
    
    raw_count = execute_query("SELECT COUNT(*) FROM ts_raw_payloads WHERE mqtt_topic = %s", (test_topic,))[0][0]
    logger.info(f"Raw Payloads Count: {raw_count} (Expected: 1)")
    if raw_count < 1:
        logger.error("❌ Data Engine didn't process the message. Make sure Data Engine is RUNNING and was restarted after schema creation!")
        return

    # 查找 Tag ID (注意：asset_path 是上一層)
    asset_path = "Test/E2E"
    tags = execute_query("SELECT tag_id, display_name FROM tags WHERE asset_path = %s", (asset_path,))
    tag_map = {name: tid for tid, name in tags}
    logger.info(f"Found Tags in DB: {tag_map}")
    
    temp_tag_id = tag_map.get('temperature')
    press_tag_id = tag_map.get('pressure')
    
    # 算一下寫了幾筆 telemetry
    temp_count = execute_query("SELECT COUNT(*) FROM ts_telemetry WHERE tag_id = %s", (temp_tag_id,))[0][0]
    press_count = execute_query("SELECT COUNT(*) FROM ts_telemetry WHERE tag_id = %s", (press_tag_id,))[0][0]
    logger.info(f"Telemetry -> Temperature: {temp_count} records, Pressure: {press_count} records.")
    
    # ----- 測試 2: Deadband 過濾 -----
    logger.info("\n[Test 2] Deadband Filtering (sending 10 duplicate temp values)")
    # schema 中 temperature 的 deadband = 0.5
    # 送 10 次 25.4 (差 0.1 < 0.5，會被過濾)
    for _ in range(10):
        publish.single(test_topic, json.dumps({"temperature": 25.4, "pressure": 2.1}), hostname="localhost")
    time.sleep(2)
    
    raw_count_after = execute_query("SELECT COUNT(*) FROM ts_raw_payloads WHERE mqtt_topic = %s", (test_topic,))[0][0]
    temp_count_after = execute_query("SELECT COUNT(*) FROM ts_telemetry WHERE tag_id = %s", (temp_tag_id,))[0][0]
    
    logger.info(f"Raw Payloads Count after 10 dupes: {raw_count_after} (Expected: 11)")
    logger.info(f"Temperature Telemetry Count after 10 dupes: {temp_count_after} (Expected: same as before, no new records)")
    
    if raw_count_after == 11 and temp_count_after == temp_count:
        logger.info("\n✅ ALL TESTS PASSED! Deadband successfully filtered duplicate telemetry while Raw Storage kept all data.")
    else:
        logger.error("\n❌ TESTS FAILED. Check constraints.")

if __name__ == "__main__":
    verify()
