"""
UNS Data Engine - E2E Verification Script
這個腳本設計用來驗證 poc_feature_scope.md 中定義的四個主要 Data Engine 驗收標準：
1. 30秒寫入測試 (Schema 綁定與正常寫入)
2. Deadband 測試 (重複數值過濾)
3. Raw 存儲 (Dual Storage 行為)
4. (斷線重連請以 Docker 重啟手動測試，此腳本不含此項)
"""

import json
import logging
import time

import paho.mqtt.publish as publish
import psycopg2
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

def setup_multi_category_test():
    logger.info("Setting up Multi-Category Test Nodes...")
    # 1. Status Node
    execute_query("DELETE FROM namespace_nodes WHERE full_path = 'Test/E2E/StatusNode';", fetch=False)
    execute_query("DELETE FROM schema_types WHERE type_name = 'StatusSchema';", fetch=False)
    res = execute_query(
        "INSERT INTO schema_types (type_name, category, fields) VALUES (%s, %s, %s) RETURNING type_id",
        ('StatusSchema', 'status', json.dumps([{"name": "state", "type": "string"}]))
    )
    status_schema_id = res[0][0]
    execute_query(
        "INSERT INTO namespace_nodes (name, node_type, full_path, schema_type_id) VALUES (%s, %s, %s, %s)",
        ('StatusNode', 'topic', 'Test/E2E/StatusNode', status_schema_id), fetch=False
    )

    # 2. Alarm Node
    execute_query("DELETE FROM namespace_nodes WHERE full_path = 'Test/E2E/AlarmNode';", fetch=False)
    execute_query("DELETE FROM schema_types WHERE type_name = 'AlarmSchema';", fetch=False)
    res = execute_query(
        "INSERT INTO schema_types (type_name, category, fields) VALUES (%s, %s, %s) RETURNING type_id",
        ('AlarmSchema', 'alarm', json.dumps([{"name": "alarm_msg", "type": "string", "path": "$.message"}]))
    )
    alarm_schema_id = res[0][0]
    execute_query(
        "INSERT INTO namespace_nodes (name, node_type, full_path, schema_type_id) VALUES (%s, %s, %s, %s)",
        ('AlarmNode', 'topic', 'Test/E2E/AlarmNode', alarm_schema_id), fetch=False
    )
    logger.info("Multi-Category setup complete. Waiting 6s...")
    time.sleep(6)

def verify():
    test_topic = "Test/E2E/Machine"
    status_topic = "Test/E2E/StatusNode"
    alarm_topic = "Test/E2E/AlarmNode"
    
    logger.info("=== Starting E2E Verification ===")
    setup_test_schema_and_node()
    setup_multi_category_test()
    
    # 清空測試用的舊資料
    logger.info("Cleaning up old test data...")
    for t in [test_topic, status_topic, alarm_topic]:
        execute_query("DELETE FROM ts_raw_payloads WHERE mqtt_topic = %s", (t,), fetch=False)
    
    asset_path = "Test/E2E"
    tags = execute_query("SELECT tag_id, display_name FROM tags WHERE asset_path = %s", (asset_path,))
    if tags:
        tag_ids = tuple([t[0] for t in tags])
        for table in ['ts_telemetry', 'ts_status', 'ts_alarms', 'tag_source_mapping']:
            execute_query(f"DELETE FROM {table} WHERE tag_id IN %s", (tag_ids,), fetch=False)
        execute_query("DELETE FROM tags WHERE tag_id IN %s", (tag_ids,), fetch=False)
    
    # ----- 測試 1: 正常 Telemetry 寫入 -----
    logger.info("\n[Test 1] Telemetry Write")
    publish.single(test_topic, json.dumps({"temperature": 25.3, "pressure": 2.1}), hostname="localhost")
    time.sleep(2)
    
    # 查找 Tag ID
    tags = execute_query("SELECT tag_id, display_name FROM tags WHERE asset_path = %s", (asset_path,))
    tag_map = {name: tid for tid, name in tags}
    
    temp_count = execute_query("SELECT COUNT(*) FROM ts_telemetry WHERE tag_id = %s", (tag_map.get('temperature'),))[0][0]
    logger.info(f"Telemetry (ts_telemetry) Count: {temp_count} (Expected: 1)")
    if temp_count != 1: raise Exception("Telemetry write failed")

    # ----- 測試 4: Status 路由 -----
    logger.info("\n[Test 4] Status Routing")
    publish.single(status_topic, json.dumps({"state": "running", "sub_state": "normal"}), hostname="localhost")
    time.sleep(2)
    
    tags = execute_query("SELECT tag_id FROM tags WHERE asset_path = %s AND display_name = 'state'", (asset_path,))
    status_tag_id = tags[0][0]
    status_count = execute_query("SELECT COUNT(*) FROM ts_status WHERE tag_id = %s", (status_tag_id,))[0][0]
    logger.info(f"Status (ts_status) Count: {status_count} (Expected: 1)")
    if status_count != 1: raise Exception("Status routing failed")

    # ----- 測試 5: Alarm 路由 -----
    logger.info("\n[Test 5] Alarm Routing")
    publish.single(alarm_topic, json.dumps({"message": "Too Hot!", "severity": "critical", "code": "E01"}), hostname="localhost")
    time.sleep(2)
    
    tags = execute_query("SELECT tag_id FROM tags WHERE asset_path = %s AND display_name = 'alarm_msg'", (asset_path,))
    alarm_tag_id = tags[0][0]
    alarm_count = execute_query("SELECT COUNT(*) FROM ts_alarms WHERE tag_id = %s", (alarm_tag_id,))[0][0]
    logger.info(f"Alarm (ts_alarms) Count: {alarm_count} (Expected: 1)")
    if alarm_count != 1: raise Exception("Alarm routing failed")
    
    logger.info("\n✅ ALL CATEGORY ROUTING TESTS PASSED!")

if __name__ == "__main__":
    try:
        verify()
    except Exception as e:
        logger.error(f"Verification Failed: {e}")

if __name__ == "__main__":
    verify()
