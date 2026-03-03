"""
Namespace Service — Business logic for Namespace CRUD
"""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NamespaceNode, Tag, TagSourceMapping, TagChangeLog


async def get_tree(db: AsyncSession) -> list[NamespaceNode]:
    """取得完整 Namespace Tree（排除 soft-deleted）。"""
    result = await db.execute(
        select(NamespaceNode)
        .where(NamespaceNode.deleted_at.is_(None))
        .order_by(NamespaceNode.full_path)
    )
    return list(result.scalars().all())


def _build_tree(nodes: list[NamespaceNode]) -> list[dict]:
    """將扁平 node list 組成巢狀 tree。"""
    node_map: dict[int, dict] = {}
    roots: list[dict] = []

    for n in nodes:
        node_map[n.node_id] = {
            "node_id": n.node_id,
            "parent_id": n.parent_id,
            "name": n.name,
            "node_type": n.node_type,
            "full_path": n.full_path,
            "schema_type_id": n.schema_type_id,
            "persist_mode": n.persist_mode,
            "retention_days": n.retention_days,
            "description": n.description,
            "created_at": n.created_at,
            "updated_at": n.updated_at,
            "children": [],
        }

    for n in nodes:
        d = node_map[n.node_id]
        if n.parent_id and n.parent_id in node_map:
            node_map[n.parent_id]["children"].append(d)
        else:
            roots.append(d)

    return roots


async def get_tree_nested(db: AsyncSession) -> list[dict]:
    """取得 Namespace Tree（巢狀結構）。"""
    nodes = await get_tree(db)
    return _build_tree(nodes)


async def create_node(
    db: AsyncSession,
    parent_id: int | None,
    name: str,
    node_type: str,
    description: str | None = None,
    schema_type_id: int | None = None,
) -> NamespaceNode:
    """建立 Namespace Node。"""
    # 計算 full_path
    if parent_id:
        parent = await db.get(NamespaceNode, parent_id)
        if not parent or parent.deleted_at:
            raise ValueError(f"Parent node {parent_id} not found")
        full_path = f"{parent.full_path}/{name}"
    else:
        full_path = name

    node = NamespaceNode(
        parent_id=parent_id,
        name=name,
        node_type=node_type,
        full_path=full_path,
        description=description,
        schema_type_id=schema_type_id,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def rename_node(db: AsyncSession, node_id: int, new_name: str) -> NamespaceNode:
    """重新命名 Node（更新 full_path + 所有子 node 的 full_path）。"""
    node = await db.get(NamespaceNode, node_id)
    if not node or node.deleted_at:
        raise ValueError(f"Node {node_id} not found")

    old_path = node.full_path
    # 計算新 path
    parts = old_path.rsplit("/", 1)
    new_path = f"{parts[0]}/{new_name}" if len(parts) > 1 else new_name

    node.name = new_name
    node.full_path = new_path
    node.updated_at = datetime.now()

    # 更新所有子 node 的 full_path
    await _update_children_paths(db, old_path, new_path)

    await db.commit()
    await db.refresh(node)
    return node


async def move_node(db: AsyncSession, node_id: int, new_parent_id: int) -> NamespaceNode:
    """
    移動 Node 到新 parent。
    觸發 Live Migration：更新 tag_source_mapping + 產生 audit log。
    """
    node = await db.get(NamespaceNode, node_id)
    if not node or node.deleted_at:
        raise ValueError(f"Node {node_id} not found")

    new_parent = await db.get(NamespaceNode, new_parent_id)
    if not new_parent or new_parent.deleted_at:
        raise ValueError(f"New parent node {new_parent_id} not found")

    old_path = node.full_path
    new_path = f"{new_parent.full_path}/{node.name}"

    # 更新 node
    node.parent_id = new_parent_id
    node.full_path = new_path
    node.updated_at = datetime.now()

    # 更新所有子 node 的 full_path
    await _update_children_paths(db, old_path, new_path)

    # ─── Live Migration：處理相關 Tags ────────────────────
    await _live_migrate_tags(db, old_path, new_path)

    await db.commit()
    await db.refresh(node)
    return node


async def soft_delete_node(db: AsyncSession, node_id: int) -> NamespaceNode:
    """Soft delete Node（標記 deleted_at）。"""
    node = await db.get(NamespaceNode, node_id)
    if not node:
        raise ValueError(f"Node {node_id} not found")

    now = datetime.now()
    node.deleted_at = now
    node.updated_at = now

    # 同時 soft delete 所有子 node
    result = await db.execute(
        select(NamespaceNode).where(
            NamespaceNode.full_path.like(f"{node.full_path}/%"),
            NamespaceNode.deleted_at.is_(None),
        )
    )
    for child in result.scalars():
        child.deleted_at = now
        child.updated_at = now

    await db.commit()
    await db.refresh(node)
    return node


async def update_persistence(
    db: AsyncSession, node_id: int, persist_mode: str, retention_days: int
) -> NamespaceNode:
    """更新 topic node 的 persist_mode / retention_days。"""
    node = await db.get(NamespaceNode, node_id)
    if not node or node.deleted_at:
        raise ValueError(f"Node {node_id} not found")
    if node.node_type != "topic":
        raise ValueError(f"Node {node_id} is not a topic node")

    node.persist_mode = persist_mode
    node.retention_days = retention_days
    node.updated_at = datetime.now()

    await db.commit()
    await db.refresh(node)
    return node


# ─── Internal helpers ─────────────────────────────────────────


async def _update_children_paths(
    db: AsyncSession, old_prefix: str, new_prefix: str
) -> None:
    """遞迴更新所有子 node 的 full_path。"""
    result = await db.execute(
        select(NamespaceNode).where(
            NamespaceNode.full_path.like(f"{old_prefix}/%")
        )
    )
    for child in result.scalars():
        child.full_path = new_prefix + child.full_path[len(old_prefix):]
        child.updated_at = datetime.now()


async def _live_migrate_tags(
    db: AsyncSession, old_path_prefix: str, new_path_prefix: str
) -> None:
    """
    Live Migration：
    1. 找到所有 old_path 下的 tag_source_mapping（active）
    2. Deactivate 舊 mapping
    3. 建立新 mapping
    4. 更新 tags.asset_path
    5. 寫 audit log
    """
    # 找出受影響的 tags
    result = await db.execute(
        select(Tag).where(
            Tag.asset_path.like(f"{old_path_prefix}%")
        )
    )
    tags = list(result.scalars().all())

    for tag in tags:
        new_asset_path = new_path_prefix + tag.asset_path[len(old_path_prefix):]

        # Deactivate 舊 mapping
        await db.execute(
            update(TagSourceMapping)
            .where(TagSourceMapping.tag_id == tag.tag_id, TagSourceMapping.active.is_(True))
            .values(active=False)
        )

        # 計算新 MQTT topic（asset_path + category）
        old_topic_base = f"{tag.asset_path}/{tag.category}"
        new_topic_base = f"{new_asset_path}/{tag.category}"
        if tag.data_point:
            old_topic = f"{old_topic_base}/{tag.data_point}"
            new_topic = f"{new_topic_base}/{tag.data_point}"
        else:
            old_topic = old_topic_base
            new_topic = new_topic_base

        # 建立新 mapping
        new_mapping = TagSourceMapping(
            tag_id=tag.tag_id,
            mqtt_topic=new_topic,
            active=True,
            mapped_by="migration_engine",
            notes=f"Live migration: {old_path_prefix} → {new_path_prefix}",
        )
        db.add(new_mapping)

        # 更新 tag 的 asset_path
        tag.asset_path = new_asset_path

        # Audit log
        log_entry = TagChangeLog(
            tag_id=tag.tag_id,
            change_type="remap",
            old_value=old_topic,
            new_value=new_topic,
            reason=f"Node move: {old_path_prefix} → {new_path_prefix}",
            changed_by="migration_engine",
        )
        db.add(log_entry)
