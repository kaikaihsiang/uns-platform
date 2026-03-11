import pytest
import json
from src.pipeline import Pipeline
from src.schema_matcher import SchemaMatcher
from src.db_writer import DBWriter

def test_pipeline_telemetry_flow(real_db_pool, sample_payloads):
    """
    E2E Pipeline Test: Validates the flow from MQTT Payload to ts_telemetry table.
    """
    topic = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Telemetry"
    payload = sample_payloads[topic]
    
    # 1. Setup Master Data in uns_test
    with real_db_pool.connection() as conn:
        cur = conn.cursor()
        # Create Schema
        cur.execute(
            """INSERT INTO uns_payload_schemas (schema_name, schema_category, fields) 
               VALUES (%s, %s, %s) RETURNING schema_id""",
            ("Test_Telemetry", "telemetry", json.dumps([
                {"name": "temp", "path": "$.data.values.temp", "type": "float", "extract": True, "persist": True}
            ]))
        )
        schema_id = cur.fetchone()[0]
        
        # Create Topic Node
        cur.execute(
            """INSERT INTO namespace_nodes (name, node_type, full_path, schema_id) 
               VALUES (%s, %s, %s, %s)""",
            ("Telemetry", "topic", topic, schema_id)
        )
        conn.commit()
        cur.close()

    # 2. Initialize Pipeline
    pipeline = Pipeline(db_pool=real_db_pool)
    # Matcher needs to refresh to see the new DB entries
    pipeline._schema_matcher.refresh()
    
    # 3. Process Payload
    payload_bytes = json.dumps(payload).encode('utf-8')
    pipeline.process(topic, payload_bytes)
    pipeline.flush() # Force write to DB
    
    # 4. Verification: Check if data exists in ts_telemetry
    with real_db_pool.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT t.value, tags.display_name 
               FROM ts_telemetry t
               JOIN tags ON t.tag_id = tags.tag_id
               WHERE tags.asset_path = %s""",
            (topic,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 25.5
        assert row[1] == "temp"
        cur.close()

def test_pipeline_status_flow(real_db_pool, sample_payloads):
    """
    E2E Pipeline Test: Validates status category routing and target_column mapping.
    """
    topic = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Status"
    payload = sample_payloads[topic]
    
    with real_db_pool.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO uns_payload_schemas (schema_name, schema_category, fields) 
               VALUES (%s, %s, %s) RETURNING schema_id""",
            ("Test_Status", "status", json.dumps([
                {"name": "state", "path": "$.data.state_code", "type": "string", "target_column": "state_code"},
                {"name": "mode", "path": "$.data.mode", "type": "string", "target_column": "mode"}
            ]))
        )
        schema_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO namespace_nodes (name, node_type, full_path, schema_id) VALUES (%s, %s, %s, %s)",
            ("Status", "topic", topic, schema_id)
        )
        conn.commit()
        cur.close()

    pipeline = Pipeline(db_pool=real_db_pool)
    pipeline._schema_matcher.refresh()
    
    pipeline.process(topic, json.dumps(payload).encode('utf-8'))
    pipeline.flush()
    
    with real_db_pool.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT state_code, mode FROM ts_status")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "PRODUCTION"
        assert row[1] == "AUTO"
        cur.close()
