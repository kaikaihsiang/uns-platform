import sys

import requests

API_BASE = "http://localhost:8000/api/v1"

def get_node_by_full_path(full_path):
    """取得現有節點。"""
    resp = requests.get(f"{API_BASE}/namespace/nodes/by-path", params={"path": full_path})
    if resp.status_code == 200:
        return resp.json()["node_id"]
    return None

def create_node(name, parent_id=None, node_type="structural", schema_id=None):
    # Check if node exists at this level
    resp = requests.get(f"{API_BASE}/namespace/nodes")
    if resp.status_code == 200:
        nodes = resp.json()
        for n in nodes:
            # Handle root nodes (parent_id is None or null)
            db_parent = n.get('parent_id')
            if n['name'] == name and db_parent == parent_id:
                print(f"ℹ Node '{name}' already exists (ID: {n['node_id']}).")
                return n['node_id']

    try:
        payload = {
            "name": name,
            "parent_id": parent_id,
            "node_type": node_type,
            "schema_id": schema_id
        }
        resp = requests.post(f"{API_BASE}/namespace/nodes", json=payload)
        if resp.status_code == 500 and "already exists" in resp.text:
             # Fallback: find it again if we hit a race or check failed
             resp = requests.get(f"{API_BASE}/namespace/nodes")
             for n in resp.json():
                 if n['name'] == name and n.get('parent_id') == parent_id:
                     return n['node_id']
        resp.raise_for_status()
        return resp.json()["node_id"]
    except requests.exceptions.HTTPError as e:
        print(f"Failed to create node {name}. Error: {e.response.text}")
        sys.exit(1)

def get_schema_id_by_name(name):
    """取得現有 Schema ID。"""
    resp = requests.get(f"{API_BASE}/payload-schemas/")
    if resp.status_code == 200:
        schemas = resp.json()
        for s in schemas:
            if s['schema_name'] == name:
                return s['schema_id']
    return None

def create_schema(name, category, decoder="json", timestamp_field=None, store_raw=True, fields=None):
    """建立 Schema，如果已存在則返回現有 ID。"""
    if fields is None:
        fields = []
    existing_id = get_schema_id_by_name(name)
    if existing_id:
        print(f"ℹ Schema '{name}' already exists (ID: {existing_id}).")
        return existing_id

    payload = {
        "schema_name": name,
        "schema_category": category,
        "decoder": decoder,
        "timestamp_field": timestamp_field,
        "store_raw": store_raw,
        "fields": fields
    }
    resp = requests.post(f"{API_BASE}/payload-schemas/", json=payload)
    if resp.status_code != 201:
        print(f"❌ Failed to create schema '{name}': {resp.status_code} {resp.text}")
    resp.raise_for_status()
    return resp.json()["schema_id"]

def main():
    print("🚀 Initializing Full-Scale Enterprise Demo Namespace (Taiwan Precision) ...")
    
    # --- 1. Schemas Definition ---
    print("\nCreating Master Schema Types...")

    # 1. Telemetry Schema (高頻率的多值遙測)
    schema_telemetry = create_schema(
        name="SMT_Mounter_Telemetry", category="telemetry", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "temp", "path": "$.data.values.temp", "type": "float", "unit": "°C", "extract": True, "persist": True, "deadband": 0.1, "array_mode": "single"},
            {"name": "press", "path": "$.data.values.press", "type": "float", "unit": "kPa", "extract": True, "persist": True, "deadband": 0.01, "array_mode": "single"},
            {"name": "vib", "path": "$.data.values.vib", "type": "float", "unit": "mm/s", "extract": True, "persist": True, "deadband": 0.01, "array_mode": "single"}
        ]
    )
    print("✓ Schema SMT_Mounter_Telemetry (telemetry) created.")

    # 2. Status Schema (SEMI E10 設備狀態機)
    schema_status = create_schema(
        name="SEMI_E10_Equipment_Status", category="status", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "state", "path": "$.data.state", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "change_only", "array_mode": "single", "target_column": "state_code"},
            {"name": "sub_state", "path": "$.data.sub_state", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "change_only", "array_mode": "single", "target_column": "sub_state_code"},
            {"name": "mode", "path": "$.data.mode", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": "change_only", "array_mode": "single", "target_column": "mode"}
        ]
    )
    print("✓ Schema SEMI_E10_Equipment_Status (status) created.")

    # 3. Alarm Schema (警報與異常 - ISA-18.2)
    schema_alarm = create_schema(
        name="SMT_Equipment_Alarm", category="alarm", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "alarm_code", "path": "$.data.alarm_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "alarm_code"},
            {"name": "severity", "path": "$.data.severity", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "severity"},
            {"name": "message", "path": "$.data.message", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "message"},
            {"name": "alarm_status", "path": "$.data.state", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "alarm_status"},
            {"name": "alarm_id", "path": "$.data.alarm_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "alarm_id"}
        ]
    )
    print("✓ Schema SMT_Equipment_Alarm (alarm) created.")

    # 4. Event Schema (生產事件 - 生產追溯)
    schema_event = create_schema(
        name="Production_Event", category="event", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "event_code", "path": "$.data.event_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "event_code"},
            {"name": "event_id", "path": "$.data.event_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "event_id"},
            {"name": "lot_id", "path": "$.data.lot_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "lot_id"},
            # {"name": "unit_id", "path": "$.data.unit_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "sample_id"}
        ]
    )
    print("✓ Schema Production_Event (event) created.")

    # 5. Measurement Schema (AOI 檢測結果)
    schema_measurement = create_schema(
        name="AOI_Inspection_Measurement", category="measurement", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "panel_id", "path": "$.data.panel_id", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "sample_id"},
            {"name": "component_ref", "path": "$.data.component_ref", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "sample_position"},
            {"name": "is_pass", "path": "$.data.is_pass", "type": "boolean", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "result"},
            {"name": "offset_x", "path": "$.data.offset_x", "type": "float", "unit": "mm", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "value"}
        ]
    )
    print("✓ Schema AOI_Inspection_Measurement (measurement) created.")

    # 6. Metrics Schema (KPI 統計)
    schema_metrics = create_schema(
        name="Equipment_OEE_Metrics", category="metrics", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "metric_category", "path": "$.data.metric_category", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "metric_category"},
            {"name": "metric_code", "path": "$.data.metric_code", "type": "string", "unit": "", "extract": True, "persist": True, "deadband": None, "array_mode": "single", "target_column": "metric_code"},
            {"name": "oee", "path": "$.data.values.oee", "type": "float", "unit": "%", "extract": True, "persist": True, "deadband": None, "array_mode": "single"},
            {"name": "avail", "path": "$.data.values.avail", "type": "float", "unit": "%", "extract": True, "persist": True, "deadband": None, "array_mode": "single"},
            {"name": "perf", "path": "$.data.values.perf", "type": "float", "unit": "%", "extract": True, "persist": True, "deadband": None, "array_mode": "single"},
            {"name": "qual", "path": "$.data.values.qual", "type": "float", "unit": "%", "extract": True, "persist": True, "deadband": None, "array_mode": "single"}
            # {"name": "oee_unit", "path": "$.data.units.oee", "type": "string", "extract": True, "persist": True, "array_mode": "single", "target_column": "details"}, 
            # {"name": "avail_unit", "path": "$.data.units.avail", "type": "string", "extract": True, "persist": True, "array_mode": "single", "target_column": "details"}, 
            # {"name": "qual_unit", "path": "$.data.units.qual", "type": "string", "extract": True, "persist": True, "array_mode": "single", "target_column": "details"}
        ]
    )
    print("✓ Schema Equipment_OEE_Metrics (metrics) created.")

    # 7. Maintenance Schema
    schema_maintenance = create_schema(
        name="Maintenance_Event", category="event", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "maintenance_id", "path": "$.data.maintenance_id", "type": "string", "extract": True, "persist": True, "target_column": "event_id"},
            {"name": "maintenance_type", "path": "$.data.type", "type": "string", "extract": True, "persist": True, "target_column": "event_code"},
            {"name": "status", "path": "$.data.status", "type": "string", "extract": True, "persist": True, "target_column": "result"},
            {"name": "message", "path": "$.data.message", "type": "string", "extract": True, "persist": True, "target_column": "details"},
        ]
    )
    print("✓ Schema Maintenance_Event (event) created.")

    # 8. Quality Schema
    schema_quality = create_schema(
        name="Quality_Sample", category="measurement", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "sample_id", "path": "$.data.sample_id", "type": "string", "extract": True, "persist": True, "target_column": "sample_id"},
            {"name": "lot_id", "path": "$.data.lot_id", "type": "string", "extract": True, "persist": True, "target_column": "lot_id"},
            {"name": "parameter_name", "path": "$.data.parameter", "type": "string", "extract": True, "persist": True, "target_column": "details"},
            {"name": "value", "path": "$.data.value", "type": "float", "extract": True, "persist": True, "target_column": "value"},
            {"name": "is_pass", "path": "$.data.is_pass", "type": "boolean", "extract": True, "persist": True, "target_column": "result"},
        ]
    )
    print("✓ Schema Quality_Sample (measurement) created.")

    # 9. Recipe Schema
    schema_recipe = create_schema(
        name="Recipe_Event", category="event", decoder="json", timestamp_field="$._meta.timestamp", store_raw=True,
        fields=[
            {"name": "recipe_id", "path": "$.data.recipe_id", "type": "string", "extract": True, "persist": True, "target_column": "event_id"},
            {"name": "event", "path": "$.data.event", "type": "string", "extract": True, "persist": True, "target_column": "event_code"},
            {"name": "source", "path": "$.data.source", "type": "string", "extract": True, "persist": True, "target_column": "details"},
        ]
    )
    print("✓ Schema Recipe_Event (event) created.")


    # --- 2. Create Hierarchy ---
    print("\nCreating ISA-95 Node Hierarchy...")
    ent_id = create_node("TaiwanPrecision")
    site_id = create_node("Taoyuan", ent_id)
    area_id = create_node("SMT_Line_1", site_id)

    # Equipment 1: Mounter
    mounter_id = create_node("SMT-Mounter-01", area_id)

    # Equipment 2: AOI
    aoi_id = create_node("SMT-AOI-01", area_id)

    print("✓ Hierarchy created (TaiwanPrecision/Taoyuan/SMT_Line_1/)")

    # --- 3. Create Topic Nodes ---
    print("\nCreating Topic Nodes and Binding Schemas...")

    # Line-Level Topics (Shared context)
    create_node("Events", area_id, "topic", schema_id=schema_event)
    create_node("QualitySamples", area_id, "topic", schema_id=schema_quality)
    create_node("RecipeEvents", area_id, "topic", schema_id=schema_recipe)

    # Mounter Topics
    create_node("Telemetry", mounter_id, "topic", schema_id=schema_telemetry)
    create_node("Status", mounter_id, "topic", schema_id=schema_status)
    create_node("Alarms", mounter_id, "topic", schema_id=schema_alarm)
    create_node("Metrics", mounter_id, "topic", schema_id=schema_metrics)
    create_node("Events", mounter_id, "topic", schema_id=schema_event)
    create_node("Maintenance", mounter_id, "topic", schema_id=schema_maintenance)

    # AOI Topics
    create_node("Measurements", aoi_id, "topic", schema_id=schema_measurement)
    create_node("Status", aoi_id, "topic", schema_id=schema_status)

    print("✓ All 9 Data Categories are successfully mapped to professional namespace topics.")

    print("\n🟢 Enterprise Namespace Seed Completed Successfully!")

if __name__ == "__main__":
    main()
