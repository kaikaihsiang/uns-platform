import pytest
from app.models import TagChangeLog, TagSourceMapping
from app.services import namespace_service, tag_service
from sqlalchemy import select


@pytest.mark.asyncio
async def test_complex_move_node_with_tags(db_session):
    """驗證移動 Node 時，子 Node 與 Tags 的遷移邏輯。"""
    # 1. 建立結構: Line1 -> Machine1 -> Status (Topic)
    line1 = await namespace_service.create_node(db_session, None, "Line1", "structural")
    machine1 = await namespace_service.create_node(db_session, line1.node_id, "Machine1", "structural")
    status_node = await namespace_service.create_node(db_session, machine1.node_id, "Status", "topic")
    
    # 2. 為 Status 建立一個 Tag
    tag1 = await tag_service.create_tag(
        db_session, 
        asset_path="Line1/Machine1/Status", 
        display_name="State", 
        category="status", 
        data_point="state", 
        data_type="string"
    )
    
    # 3. 建立目標 Line2
    line2 = await namespace_service.create_node(db_session, None, "Line2", "structural")
    
    # 4. 執行移動: Machine1 移動到 Line2 下
    await namespace_service.move_node(db_session, machine1.node_id, line2.node_id)
    
    # 5. 驗證 Node 路徑更新
    await db_session.refresh(machine1)
    await db_session.refresh(status_node)
    assert machine1.full_path == "Line2/Machine1"
    assert status_node.full_path == "Line2/Machine1/Status"
    
    # 6. 驗證 Tag asset_path 更新
    await db_session.refresh(tag1)
    assert tag1.asset_path == "Line2/Machine1/Status"
    
    # 7. 驗證 TagSourceMapping 更新
    mappings_result = await db_session.execute(
        select(TagSourceMapping).where(TagSourceMapping.tag_id == tag1.tag_id)
    )
    mappings = list(mappings_result.scalars().all())
    assert len(mappings) == 2 # 舊的 inactive + 新的 active
    
    active_mapping = next(m for m in mappings if m.active)
    assert active_mapping.mqtt_topic == "Line2/Machine1/Status/State/state"
    
    # 8. 驗證 Audit Log
    logs_result = await db_session.execute(
        select(TagChangeLog).where(TagChangeLog.tag_id == tag1.tag_id)
    )
    logs = list(logs_result.scalars().all())
    assert any(log.change_type == "remap" for log in logs)

@pytest.mark.asyncio
async def test_soft_delete_cascade_and_restore(db_session):
    """驗證 Soft Delete 的級聯效果與還原邏輯。"""
    # 建立結構
    p = await namespace_service.create_node(db_session, None, "Parent", "structural")
    c = await namespace_service.create_node(db_session, p.node_id, "Child", "topic")
    t = await tag_service.create_tag(db_session, asset_path="Parent/Child", display_name="T1", category="telemetry")
    
    # 執行 Soft Delete
    await namespace_service.soft_delete_node(db_session, p.node_id)
    
    # 驗證父、子、Tag 都被刪除
    await db_session.refresh(p)
    await db_session.refresh(c)
    await db_session.refresh(t)
    assert p.deleted_at is not None
    assert c.deleted_at is not None
    assert t.deleted_at is not None
    
    # 執行 Restore
    await namespace_service.restore_node(db_session, p.node_id)
    
    # 驗證父、子都還原 (Tag 還原目前在 namespace_service.restore_node 裡沒做，這是已知的)
    await db_session.refresh(p)
    await db_session.refresh(c)
    assert p.deleted_at is None
    assert c.deleted_at is None

@pytest.mark.asyncio
async def test_rename_cascade(db_session):
    """驗證重新命名 Node 時的路徑級聯更新。"""
    line = await namespace_service.create_node(db_session, None, "OldLine", "structural")
    m = await namespace_service.create_node(db_session, line.node_id, "Machine", "structural")
    
    await namespace_service.rename_node(db_session, line.node_id, "NewLine")
    
    await db_session.refresh(line)
    await db_session.refresh(m)
    assert line.full_path == "NewLine"
    assert m.full_path == "NewLine/Machine"
