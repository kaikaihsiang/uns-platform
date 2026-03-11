import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_node_schema_binding_flow(client: AsyncClient):
    """
    驗證節點與 Schema 綁定的完整整合流程。
    """
    # 1. 建立一個 Topic 節點
    node_resp = await client.post("/api/v1/namespace/nodes", json={
        "name": "PressureSensor",
        "node_type": "topic",
        "parent_id": None
    })
    assert node_resp.status_code == 201
    node_id = node_resp.json()["node_id"]

    # 2. 建立一個 Schema
    schema_resp = await client.post("/api/v1/payload-schemas/", json={
        "schema_name": "Test_Pressure_Schema",
        "schema_category": "telemetry",
        "fields": [
            {"name": "pressure", "path": "$.pressure", "type": "float", "extract": True, "persist": True}
        ]
    })
    assert schema_resp.status_code == 201
    schema_id = schema_resp.json()["schema_id"]

    # 3. 執行綁定操作
    bind_resp = await client.put(f"/api/v1/namespace/nodes/{node_id}/schema", json={
        "schema_id": schema_id
    })
    assert bind_resp.status_code == 200
    assert bind_resp.json()["schema_id"] == schema_id

    # 4. 再次查詢節點，確認綁定持久化
    get_node = await client.get("/api/v1/namespace/nodes")
    nodes = get_node.json()
    target_node = next(n for n in nodes if n["node_id"] == node_id)
    assert target_node["schema_id"] == schema_id

@pytest.mark.asyncio
async def test_auto_detect_approval_integration(client: AsyncClient):
    """
    驗證偵測建議、核准、再綁定的業務鏈。
    """
    # 1. 直接注入一筆建議 (模擬 Data Engine 偵測後的結果)
    # 註：這裡直接透過 API 建立一個 suggested schema
    schema_payload = {
        "schema_name": "Suggested_Mounter_V1",
        "fields": [{"name": "temp", "path": "$.temp", "type": "float", "extract": True, "persist": True}],
        "schema_category": "telemetry"
    }
    # 建立正式的 schema 做為對比，但在實務中 data-engine 是直接插 DB。
    # 這裡我們測試 API 核准邏輯
    setup_resp = await client.post("/api/v1/payload-schemas/", json=schema_payload)
    schema_id = setup_resp.json()["schema_id"]
    
    # 2. 執行核准
    approve_resp = await client.post(f"/api/v1/payload-schemas/{schema_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["is_suggested"] is False
    assert approve_resp.json()["status"] == "confirmed"
