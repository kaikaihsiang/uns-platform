from app.models import NamespaceNode, UnsPayloadSchema
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_test_data(db: AsyncSession):
    """
    注入具有工業真實感的測試資料。
    建立 TaiwanPrecision/Taoyuan/SMT_Line_1 結構與基本 Schema。
    """
    
    # 1. 建立基本 Schemas
    schemas = [
        {
            "schema_name": "SMT_Mounter_Telemetry",
            "schema_category": "telemetry",
            "fields": [
                {"name": "temp", "path": "$.data.values.temp", "type": "float", "unit": "°C", "extract": True, "persist": True},
                {"name": "press", "path": "$.data.values.press", "type": "float", "unit": "kPa", "extract": True, "persist": True}
            ]
        },
        {
            "schema_name": "SEMI_E10_Equipment_Status",
            "schema_category": "status",
            "fields": [
                {"name": "state", "path": "$.data.state", "type": "string", "target_column": "state_code"},
                {"name": "mode", "path": "$.data.mode", "type": "string", "target_column": "mode"}
            ]
        }
    ]
    
    schema_map = {}
    for s_data in schemas:
        schema = UnsPayloadSchema(**s_data)
        db.add(schema)
        await db.flush()
        schema_map[s_data["schema_name"]] = schema.schema_id

    # 2. 建立 ISA-95 階層
    # TaiwanPrecision
    root = NamespaceNode(name="TaiwanPrecision", node_type="structural", full_path="TaiwanPrecision")
    db.add(root)
    await db.flush()
    
    # Taoyuan
    site = NamespaceNode(name="Taoyuan", parent_id=root.node_id, node_type="structural", full_path="TaiwanPrecision/Taoyuan")
    db.add(site)
    await db.flush()
    
    # SMT_Line_1
    area = NamespaceNode(name="SMT_Line_1", parent_id=site.node_id, node_type="structural", full_path="TaiwanPrecision/Taoyuan/SMT_Line_1")
    db.add(area)
    await db.flush()
    
    # SMT-Mounter-01
    mounter = NamespaceNode(name="SMT-Mounter-01", parent_id=area.node_id, node_type="structural", full_path="TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01")
    db.add(mounter)
    await db.flush()
    
    # 建立 Topic Nodes
    telemetry_topic = NamespaceNode(
        name="Telemetry", 
        parent_id=mounter.node_id, 
        node_type="topic", 
        full_path="TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Telemetry",
        schema_id=schema_map["SMT_Mounter_Telemetry"]
    )
    status_topic = NamespaceNode(
        name="Status", 
        parent_id=mounter.node_id, 
        node_type="topic", 
        full_path="TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Status",
        schema_id=schema_map["SEMI_E10_Equipment_Status"]
    )
    
    db.add_all([telemetry_topic, status_topic])
    await db.commit()
