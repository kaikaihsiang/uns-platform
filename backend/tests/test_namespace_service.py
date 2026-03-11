import pytest
from app.models import NamespaceNode, Tag, TagChangeLog, TagSourceMapping
from app.services import namespace_service
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_node_path_calculation(db_session):
    """驗證建立節點時 full_path 的計算。"""
    # 取得 seed 資料中的 TaiwanPrecision/Taoyuan
    stmt = select(NamespaceNode).where(NamespaceNode.full_path == "TaiwanPrecision/Taoyuan")
    result = await db_session.execute(stmt)
    parent = result.scalar_one()
    
    # 在 Taoyuan 下建立 Hsinchu (雖然地理上不對，但測試邏輯)
    new_node = await namespace_service.create_node(
        db_session, parent_id=parent.node_id, name="Hsinchu", node_type="structural"
    )
    
    assert new_node.full_path == "TaiwanPrecision/Taoyuan/Hsinchu"

@pytest.mark.asyncio
async def test_rename_node_recursive_update(db_session):
    """驗證重新命名節點時，子節點的 full_path 是否同步更新。"""
    # 取得 SMT_Line_1
    stmt = select(NamespaceNode).where(NamespaceNode.full_path == "TaiwanPrecision/Taoyuan/SMT_Line_1")
    result = await db_session.execute(stmt)
    area_node = result.scalar_one()
    
    # 重新命名 SMT_Line_1 -> SMT_North
    await namespace_service.rename_node(db_session, area_node.node_id, "SMT_North")
    
    # 檢查自身
    assert area_node.full_path == "TaiwanPrecision/Taoyuan/SMT_North"
    
    # 檢查子節點 (SMT-Mounter-01)
    stmt_child = select(NamespaceNode).where(NamespaceNode.name == "SMT-Mounter-01")
    result_child = await db_session.execute(stmt_child)
    child = result_child.scalar_one()
    assert child.full_path == "TaiwanPrecision/Taoyuan/SMT_North/SMT-Mounter-01"

@pytest.mark.asyncio
async def test_move_node_live_migration(db_session):
    """
    驗證移動節點時觸發的 Live Migration。
    1. full_path 更新
    2. TagSourceMapping 更新
    3. Audit Log 產生
    """
    # 1. 準備：在 SMT-Mounter-01 下建立一個 Tag
    stmt = select(NamespaceNode).where(NamespaceNode.full_path == "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01")
    mounter = (await db_session.execute(stmt)).scalar_one()
    
    tag = Tag(
        display_name="Temp",
        asset_path=mounter.full_path,
        category="Telemetry",
        data_point="T1"
    )
    db_session.add(tag)
    await db_session.flush()
    
    mapping = TagSourceMapping(
        tag_id=tag.tag_id,
        mqtt_topic=f"{mounter.full_path}/Temp/T1",
        active=True
    )
    db_session.add(mapping)
    await db_session.commit()
    
    # 2. 執行：將 SMT-Mounter-01 從 SMT_Line_1 移動到根目錄
    await namespace_service.move_node(db_session, mounter.node_id, new_parent_id=None)
    
    # 3. 驗證
    # Path
    assert mounter.full_path == "SMT-Mounter-01"
    
    # Mapping (Live Migration)
    stmt_map = select(TagSourceMapping).where(TagSourceMapping.tag_id == tag.tag_id, TagSourceMapping.active.is_(True))
    new_mapping = (await db_session.execute(stmt_map)).scalar_one()
    assert new_mapping.mqtt_topic == "SMT-Mounter-01/Temp/T1"
    
    # Old Mapping should be inactive
    stmt_old = select(TagSourceMapping).where(TagSourceMapping.tag_id == tag.tag_id, TagSourceMapping.active.is_(False))
    old_mapping = (await db_session.execute(stmt_old)).scalar_one()
    assert old_mapping.mqtt_topic == "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Temp/T1"
    
    # Audit Log
    stmt_log = select(TagChangeLog).where(TagChangeLog.tag_id == tag.tag_id)
    log = (await db_session.execute(stmt_log)).scalar_one()
    assert log.change_type == "remap"
    assert "Node move" in log.reason
