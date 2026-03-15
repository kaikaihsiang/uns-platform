import json
import time

import httpx
import paho.mqtt.publish as publish
import pytest
from sqlalchemy import create_engine, text

# --- Test Configuration ---
BASE_URL = "http://localhost:8000/api/v1"
DB_URL = "postgresql://uns_admin:uns_dev_password@localhost:5432/uns_timeseries"
TARGET_PATH = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01"

# --- Test Fixtures ---
@pytest.fixture(scope="module")
def db_engine():
    """Provide a SQLAlchemy engine to inspect the database."""
    return create_engine(DB_URL)

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown(db_engine):
    """Ensure the latest_values table is clean before the test module runs."""
    with db_engine.connect() as connection:
        connection.execute(text("TRUNCATE TABLE latest_values;"))
        connection.commit()
    yield
    # Teardown logic can be added here if needed

# --- Test Case ---
def test_e2e_industrial_lifecycle():
    """
    E2E Test: Simulates an industrial lifecycle event and verifies the snapshot.
    1. Publish a sequence of realistic data (Status, Telemetry, Alarm).
    2. Wait for the Data Engine to process.
    3. Call the GetSnapshot API.
    4. Assert the content of the response.
    """
    # 1. Publish Data: Simulate equipment starting a run, overheating, and finishing.
    publish.single(f"{TARGET_PATH}/Events", json.dumps({"data": {"event_code": "LOT_START", "lot_id": "LOT-E2E-001"}}), hostname="localhost", port=1883)
    time.sleep(0.1)

    # Status: Change to Production
    publish.single(f"{TARGET_PATH}/Status", json.dumps({"data": {"state": "PRD", "sub_state": "RUN", "mode": "AUTO"}}), hostname="localhost", port=1883)
    time.sleep(0.1)

    # Telemetry: Normal Operation
    publish.single(f"{TARGET_PATH}/Telemetry::temp", json.dumps({"value": 65.0}), hostname="localhost", port=1883)
    time.sleep(0.1)

    # Telemetry: Overheating
    publish.single(f"{TARGET_PATH}/Telemetry::temp", json.dumps({"value": 95.5}), hostname="localhost", port=1883)
    time.sleep(0.1)

    # Alarm: Triggered due to overheating
    publish.single(f"{TARGET_PATH}/Alarms", json.dumps({"data": {"alarm_code": "TEMP-HIGH", "alarm_status": "active", "severity": "major"}}), hostname="localhost", port=1883)

    # 2. Wait for processing & polling API
    print("[E2E-TEST] Polling GetSnapshot API...")
    max_retries = 10
    snapshot_data = {}
    success = False
    
    for _ in range(max_retries):
        try:
            resp = httpx.get(f"{BASE_URL}/semantic/snapshot?paths={TARGET_PATH}/**")
            resp.raise_for_status()
            snapshot_data = {item["path"]: item for item in resp.json()}
            
            status_path = f"{TARGET_PATH}/Status"
            if status_path in snapshot_data:
                status_point = snapshot_data[status_path]
                if status_point.get("display_value") == "PRD (RUN) - AUTO":
                    success = True
                    break
        except Exception:
            pass
            
        time.sleep(1) # Give Data Engine and DBWriter time to flush
        
    if not success:
        status_path = f"{TARGET_PATH}/Status"
        last_val = snapshot_data.get(status_path, {}).get("display_value", "None")
        pytest.fail(f"Failed to find state 'PRD (RUN) - AUTO' within timeout. Last value: {last_val}")

    # 4. Assertions
    print("[E2E-TEST] Asserting results...")
    
    # Check Status
    status_path = f"{TARGET_PATH}/Status"
    status_point = snapshot_data[status_path]
    assert status_point["display_value"] == "PRD (RUN) - AUTO"
    assert status_point["data"]["state_code"] == "PRD"
    assert status_point["data"]["mode"] == "AUTO"
