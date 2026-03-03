"""
Namespace CRUD API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import NodeCreate, NodeRename, NodeMove, NodePersistence, NodeOut
from app.services import namespace_service

router = APIRouter(prefix="/namespace", tags=["Namespace"])


@router.get("/tree")
async def get_namespace_tree(db: AsyncSession = Depends(get_db)):
    """取得完整 Namespace 樹狀結構（巢狀）。"""
    return await namespace_service.get_tree_nested(db)


@router.post("/nodes", response_model=NodeOut, status_code=201)
async def create_node(body: NodeCreate, db: AsyncSession = Depends(get_db)):
    """建立 Namespace Node（structural 或 topic）。"""
    try:
        node = await namespace_service.create_node(
            db,
            parent_id=body.parent_id,
            name=body.name,
            node_type=body.node_type,
            description=body.description,
            schema_type_id=body.schema_type_id,
        )
        return node
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/nodes/{node_id}/move", response_model=NodeOut)
async def move_node(node_id: int, body: NodeMove, db: AsyncSession = Depends(get_db)):
    """移動 Node（觸發 Live Migration）。"""
    try:
        return await namespace_service.move_node(db, node_id, body.new_parent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/nodes/{node_id}/rename", response_model=NodeOut)
async def rename_node(node_id: int, body: NodeRename, db: AsyncSession = Depends(get_db)):
    """重新命名 Node。"""
    try:
        return await namespace_service.rename_node(db, node_id, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/nodes/{node_id}", response_model=NodeOut)
async def delete_node(node_id: int, db: AsyncSession = Depends(get_db)):
    """Soft delete Node。"""
    try:
        return await namespace_service.soft_delete_node(db, node_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/nodes/{node_id}/persistence", response_model=NodeOut)
async def update_persistence(
    node_id: int, body: NodePersistence, db: AsyncSession = Depends(get_db)
):
    """設定 topic node 的 persist_mode / retention_days。"""
    try:
        return await namespace_service.update_persistence(
            db, node_id, body.persist_mode, body.retention_days
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
