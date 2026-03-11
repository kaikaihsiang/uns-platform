import pytest
from sqlalchemy import select
from app.models import NamespaceNode
from app.services import namespace_service

@pytest.mark.asyncio
async def test_create_node_path_generation(db_session):
    """
    驗證建立節點時 full_path 是否正確自動生成。
    """
    # 1. 建立根節點
    root = await namespace_service.create_node(db_session, parent_id=None, name="Enterprise", node_type="structural")
    assert root.full_path == "Enterprise"
    
    # 2. 建立子節點
    site = await namespace_service.create_node(db_session, parent_id=root.node_id, name="SiteA", node_type="structural")
    assert site.full_path == "Enterprise/SiteA"
    
    # 3. 建立深層節點
    line = await namespace_service.create_node(db_session, parent_id=site.node_id, name="Line1", node_type="structural")
    assert line.full_path == "Enterprise/SiteA/Line1"

@pytest.mark.asyncio
async def test_rename_node_recursive_path_update(db_session):
    """
    驗證重新命名節點時，所有子節點的 full_path 是否遞迴更新。
    """
    # 建立結構: A/B/C
    node_a = await namespace_service.create_node(db_session, None, "A", "structural")
    node_b = await namespace_service.create_node(db_session, node_a.node_id, "B", "structural")
    node_c = await namespace_service.create_node(db_session, node_b.node_id, "C", "structural")
    
    # 重新命名 A -> NewA
    await namespace_service.rename_node(db_session, node_a.node_id, "NewA")
    
    # 重新整理物件狀態
    await db_session.refresh(node_a)
    await db_session.refresh(node_b)
    await db_session.refresh(node_c)
    
    assert node_a.full_path == "NewA"
    assert node_b.full_path == "NewA/B"
    assert node_c.full_path == "NewA/B/C"

@pytest.mark.asyncio
async def test_move_node_recursive_path_update(db_session):
    """
    驗證移動節點（更改 Parent）時，子樹的路徑是否正確更新。
    """
    # 建立結構: 
    # Root1/A/B
    # Root2/
    r1 = await namespace_service.create_node(db_session, None, "Root1", "structural")
    r2 = await namespace_service.create_node(db_session, None, "Root2", "structural")
    node_a = await namespace_service.create_node(db_session, r1.node_id, "A", "structural")
    node_b = await namespace_service.create_node(db_session, node_a.node_id, "B", "structural")
    
    # 將 A 從 Root1 移動到 Root2
    await namespace_service.move_node(db_session, node_a.node_id, r2.node_id)
    
    await db_session.refresh(node_a)
    await db_session.refresh(node_b)
    
    assert node_a.parent_id == r2.node_id
    assert node_a.full_path == "Root2/A"
    assert node_b.full_path == "Root2/A/B"

@pytest.mark.asyncio
async def test_move_node_to_root(db_session):
    """
    驗證將節點移動到根層級時路徑是否正確。
    """
    r1 = await namespace_service.create_node(db_session, None, "Root1", "structural")
    node_a = await namespace_service.create_node(db_session, r1.node_id, "A", "structural")
    
    # 將 A 移動到根
    await namespace_service.move_node(db_session, node_a.node_id, None)
    
    await db_session.refresh(node_a)
    assert node_a.parent_id is None
    assert node_a.full_path == "A"
