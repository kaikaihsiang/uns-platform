import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1"

def create_node(name, parent_id=None, node_type="structural", schema_type_id=None):
    # Check if exists
    try:
        resp = requests.get(f"{API_BASE}/namespace/nodes")
        if resp.status_code == 200:
            nodes = resp.json()
            for n in nodes:
                if n['name'] == name and n.get('parent_id') == parent_id:
                    print(f"ℹ Node '{name}' already exists.")
                    return n['node_id']
    except:
        pass

    resp = requests.post(f"{API_BASE}/namespace/nodes", json={
        "name": name,
        "parent_id": parent_id,
        "node_type": node_type,
        "schema_type_id": schema_type_id
    })
    if resp.status_code == 500 and "already exists" in resp.text:
        # Fallback
        nodes = requests.get(f"{API_BASE}/namespace/nodes").json()
        for n in nodes:
            if n['name'] == name and n.get('parent_id') == parent_id:
                return n['node_id']
    
    resp.raise_for_status()
    return resp.json()["node_id"]

def create_schema(name, decoder, timestamp_field, store_raw, mismatch, new_field, fields, category="telemetry"):
    # Check if exists
    resp = requests.get(f"{API_BASE}/payload-schemas/")
    if resp.status_code == 200:
        schemas = resp.json()
        for s in schemas:
            if s['schema_name'] == name:
                print(f"ℹ Schema '{name}' already exists.")
                return s['schema_id']

    payload = {
        "schema_name": name,
        "schema_category": category,
        "decoder": decoder,
        "timestamp_field": timestamp_field,
        "store_raw": store_raw,
        "raw_retention_days": 30,
        "on_schema_mismatch": mismatch,
        "on_new_field": new_field,
        "fields": fields
    }
    resp = requests.post(f"{API_BASE}/payload-schemas/", json=payload)
    resp.raise_for_status()
    return resp.json()["schema_id"]

def main():
    print("Initializing Enterprise Demo Data (ISA-95) with Event Schemas...")
    
    # 1. Create Hierarchy
    ent_id = create_node("TaiwanPrecision")
    site_id = create_node("Taoyuan", ent_id)
    area_id = create_node("SMT", site_id)
    line_id = create_node("Line1", area_id)
    
    equip_id = create_node("Printer", line_id)
    mes_node_id = create_node("MES", line_id) # For L3/L4 lot events
    
    # Create Event structural folders under equipment
    equip_event_node_id = create_node("Event", equip_id)
    mes_event_node_id = create_node("Event", mes_node_id)

    print("✓ Created ISA-95 Node Hierarchy.")
    
    # 2. Schemas Definition

    # 2.1 Telemetry Schema (Continuous Data)
    schema_telemetry = create_schema(
        name="SMT_Printer_Telemetry", decoder="json", timestamp_field="$._meta.timestamp",
        store_raw=True, mismatch="log_and_store", new_field="suggest", category="telemetry",
        fields=[
            {"name": "temperature", "path": "$.temperature", "type": "float", "unit": "°C", "extract": True, "persist": True, "deadband": "0.1", "array_mode": "single"},
            {"name": "pressure", "path": "$.pressure", "type": "float", "unit": "kPa", "extract": True, "persist": True, "deadband": "0.05", "array_mode": "single"},
            {"name": "recipe_name", "path": "$.recipe_name", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "change_only", "array_mode": "single"},
            {"name": "humidity", "path": "$.humidity", "type": "float", "unit": "%", "extract": True, "persist": False, "deadband": "null", "array_mode": "single"}
        ]
    )
    print(f"✓ Created Schema: SMT_Printer_Telemetry (ID: {schema_telemetry})")

    # 2.2 Event: Process (Machine operations)
    schema_event_process = create_schema(
        name="Equipment_Event_Process", decoder="json", timestamp_field="$._meta.timestamp",
        store_raw=True, mismatch="log_and_store", new_field="suggest", category="event",
        fields=[
            {"name": "event_code", "path": "$.data.event_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "lot_id", "path": "$.data.lot_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "recipe_id", "path": "$.data.recipe_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "duration_seconds", "path": "$.data.duration_seconds", "type": "float", "unit": "s", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "result", "path": "$.data.result", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "operator", "path": "$.data.operator", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"}
        ]
    )
    print(f"✓ Created Schema: Equipment_Event_Process (ID: {schema_event_process})")

    # 2.3 Event: Recipe (Recipe Management)
    schema_event_recipe = create_schema(
        name="Equipment_Event_Recipe", decoder="json", timestamp_field="$._meta.timestamp",
        store_raw=True, mismatch="log_and_store", new_field="suggest", category="event",
        fields=[
            {"name": "event_code", "path": "$.data.event_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "recipe_id", "path": "$.data.recipe_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "version", "path": "$.data.version", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "approved_by", "path": "$.data.approved_by", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"}
        ]
    )
    print(f"✓ Created Schema: Equipment_Event_Recipe (ID: {schema_event_recipe})")

    # 2.4 Event: Lot (MES Production Context)
    schema_event_lot = create_schema(
        name="MES_Event_Lot", decoder="json", timestamp_field="$._meta.timestamp",
        store_raw=True, mismatch="log_and_store", new_field="suggest", category="event",
        fields=[
            {"name": "event_code", "path": "$.data.event_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "lot_id", "path": "$.data.lot_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "product_name", "path": "$.data.product_name", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "qty", "path": "$.data.qty", "type": "integer", "unit": "pcs", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "target_equipment", "path": "$.data.target_equipment", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"}
        ]
    )
    print(f"✓ Created Schema: MES_Event_Lot (ID: {schema_event_lot})")

    # 2.5 Event: Quality (QMS Quality System)
    schema_event_quality = create_schema(
        name="MES_Event_Quality", decoder="json", timestamp_field="$._meta.timestamp",
        store_raw=True, mismatch="log_and_store", new_field="suggest", category="event",
        fields=[
            {"name": "event_code", "path": "$.data.event_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "lot_id", "path": "$.data.lot_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "hold_reason", "path": "$.data.hold_reason", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"},
            {"name": "disposition", "path": "$.data.disposition", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "null", "array_mode": "single"}
        ]
    )
    print(f"✓ Created Schema: MES_Event_Quality (ID: {schema_event_quality})")

    # 3. Create Topic Nodes mapped to corresponding Schemas
    
    # 3.1 Printer/Telemetry
    create_node("Telemetry", equip_id, "topic", schema_type_id=schema_telemetry)
    
    # 3.2 Printer/Event/*
    create_node("Process", equip_event_node_id, "topic", schema_type_id=schema_event_process)
    create_node("Recipe", equip_event_node_id, "topic", schema_type_id=schema_event_recipe)
    
    # 3.3 MES/Event/*
    create_node("Lot", mes_event_node_id, "topic", schema_type_id=schema_event_lot)
    create_node("Quality", mes_event_node_id, "topic", schema_type_id=schema_event_quality)

    print("✓ All Topic Nodes and Event Categories correctly mapped.")
    
    print("Enterprise demo seed data initialized successfully.")

if __name__ == "__main__":
    main()
