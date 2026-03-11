import pytest
from sqlalchemy import select
from app.models import NamespaceNode

@pytest.mark.asyncio
async def test_write_node(db_session):
    """測試寫入資料。"""
    node = NamespaceNode(
        name="IsolatedNode",
        node_type="structural",
        full_path="IsolatedNode"
    )
    db_session.add(node)
    await db_session.commit()
    
    # 驗證是否寫入
    result = await db_session.execute(select(NamespaceNode).where(NamespaceNode.name == "IsolatedNode"))
    assert result.scalar_one_or_none() is not None

@pytest.mark.asyncio
async def test_node_is_gone(db_session):
    """驗證上一個測試的資料已經被清空。"""
    result = await db_session.execute(select(NamespaceNode).where(NamespaceNode.name == "IsolatedNode"))
    assert result.scalar_one_or_none() is None
