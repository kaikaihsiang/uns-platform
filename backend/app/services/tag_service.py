"""
Tag Service — Tag CRUD, auto mapping, and query
"""
from datetime import datetime, timezone

from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tag, TagSourceMapping, TagChangeLog, TsTelemetry


# ═══════════════════════════════════════════════════════════════
# Tag CRUD
# ═══════════════════════════════════════════════════════════════


async def create_tag(
    db: AsyncSession,
    display_name: str,
    asset_path: str,
    category: str,
    data_point: str | None = None,
    unit: str | None = None,
    data_type: str = "float",
    description: str | None = None,
) -> Tag:
    """
    建立 Tag + 自動建立 tag_source_mapping。
    MQTT topic = asset_path/category[/data_point]
    """
    tag = Tag(
        display_name=display_name,
        asset_path=asset_path,
        category=category,
        data_point=data_point,
        unit=unit,
        data_type=data_type,
        description=description,
    )
    db.add(tag)
    await db.flush()  # 取得 tag_id

    # Auto-create tag_source_mapping
    mqtt_topic = f"{asset_path}/{category}"
    if data_point:
        mqtt_topic = f"{mqtt_topic}/{data_point}"

    mapping = TagSourceMapping(
        tag_id=tag.tag_id,
        mqtt_topic=mqtt_topic,
        active=True,
        mapped_by="auto",
        notes="Auto-created with tag",
    )
    db.add(mapping)

    # Audit log
    log = TagChangeLog(
        tag_id=tag.tag_id,
        change_type="create",
        new_value=mqtt_topic,
        reason="Tag created",
        changed_by="api",
    )
    db.add(log)

    await db.commit()
    await db.refresh(tag)
    return tag


async def update_tag(db: AsyncSession, tag_id: int, **kwargs) -> Tag:
    """
    更新 Tag 並詳細記錄變更內容。
    """
    tag = await db.get(Tag, tag_id)
    if not tag or tag.deleted_at is not None:
        raise ValueError(f"Tag {tag_id} not found")

    changes = []
    for key, new_value in kwargs.items():
        # 僅處理 Tag 模型中存在的屬性
        if not hasattr(tag, key):
            continue
            
        old_value = getattr(tag, key)
        
        # 僅在數值真正發生變動時記錄 (排除 None 且值相同的更新)
        if new_value is not None and new_value != old_value:
            changes.append(f"{key}: {old_value} -> {new_value}")
            setattr(tag, key, new_value)

    # 如果沒有任何欄位變動，直接回傳
    if not changes:
        return tag

    # Audit log: 記錄詳細的變更內容
    log = TagChangeLog(
        tag_id=tag_id,
        change_type="update",
        reason=f"變更明細: {'; '.join(changes)}",
        changed_by="api",
    )
    db.add(log)

    await db.commit()
    await db.refresh(tag)
    return tag


async def get_tag(db: AsyncSession, tag_id: int) -> Tag | None:
    """取得單一 Tag。"""
    return await db.get(Tag, tag_id)


async def list_tags_by_path(db: AsyncSession, node_path: str, recursive: bool = False) -> list[Tag]:
    """取得某 asset_path 底下的所有 Tag。"""
    stmt = select(Tag).where(Tag.deleted_at == None)
    
    if recursive:
        stmt = stmt.where(Tag.asset_path.like(f"{node_path}%"))
    else:
        stmt = stmt.where(Tag.asset_path == node_path)
        
    stmt = stmt.order_by(Tag.asset_path, Tag.category, Tag.data_point)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tag_mappings(db: AsyncSession, tag_id: int) -> list[TagSourceMapping]:
    """取得 Tag 的所有 source mapping（含歷史）。"""
    result = await db.execute(
        select(TagSourceMapping)
        .where(TagSourceMapping.tag_id == tag_id)
        .order_by(desc(TagSourceMapping.mapped_at))
    )
    return list(result.scalars().all())


async def get_tag_history(db: AsyncSession, tag_id: int) -> list[TagChangeLog]:
    """取得 Tag 的變更歷史（audit log）。"""
    result = await db.execute(
        select(TagChangeLog)
        .where(TagChangeLog.tag_id == tag_id)
        .order_by(desc(TagChangeLog.changed_at))
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════
# Tag Value Queries
# ═══════════════════════════════════════════════════════════════


async def get_tag_values(
    db: AsyncSession,
    tag_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 1000,
) -> list[TsTelemetry]:
    """查詢 Tag 的歷史時序資料（by tag_id，跨 migration）。"""
    stmt = select(TsTelemetry).where(TsTelemetry.tag_id == tag_id)

    if start:
        stmt = stmt.where(TsTelemetry.time >= start)
    if end:
        stmt = stmt.where(TsTelemetry.time <= end)

    stmt = stmt.order_by(desc(TsTelemetry.time)).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tag_latest(db: AsyncSession, tag_id: int) -> TsTelemetry | None:
    """查詢 Tag 的最新一筆資料。"""
    result = await db.execute(
        select(TsTelemetry)
        .where(TsTelemetry.tag_id == tag_id)
        .order_by(desc(TsTelemetry.time))
        .limit(1)
    )
    return result.scalars().first()


async def get_values_by_topic(
    db: AsyncSession,
    mqtt_topic: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 1000,
) -> list[TsTelemetry]:
    """
    用 MQTT topic 查詢歷史資料。
    先找 tag_source_mapping 取得 tag_id，再查 ts_telemetry。
    注意：只查該 mapping 期間的資料。
    """
    # 找到 mapping
    result = await db.execute(
        select(TagSourceMapping).where(TagSourceMapping.mqtt_topic == mqtt_topic)
    )
    mapping = result.scalars().first()
    if not mapping:
        return []

    stmt = select(TsTelemetry).where(TsTelemetry.tag_id == mapping.tag_id)

    if start:
        stmt = stmt.where(TsTelemetry.time >= start)
    if end:
        stmt = stmt.where(TsTelemetry.time <= end)

    # 限制到 mapping 的有效期間
    stmt = stmt.where(TsTelemetry.time >= mapping.mapped_at)

    stmt = stmt.order_by(desc(TsTelemetry.time)).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════
# Recycle Bin
# ═══════════════════════════════════════════════════════════════


async def soft_delete_tag(db: AsyncSession, tag_id: int) -> Tag:
    """Soft delete Tag。"""
    tag = await db.get(Tag, tag_id)
    if not tag or tag.deleted_at is not None:
        raise ValueError(f"Tag {tag_id} not found")

    tag.deleted_at = datetime.now(timezone.utc)

    # Audit log
    log = TagChangeLog(
        tag_id=tag.tag_id,
        change_type="delete",
        reason="Soft delete tag",
        changed_by="api",
    )
    db.add(log)

    await db.commit()
    await db.refresh(tag)
    return tag


async def get_deleted_tags(db: AsyncSession) -> list[Tag]:
    """取得所有 Soft-deleted 的 Tags。"""
    result = await db.execute(
        select(Tag)
        .where(Tag.deleted_at != None)
        .order_by(desc(Tag.deleted_at))
    )
    return list(result.scalars().all())


async def restore_tag(db: AsyncSession, tag_id: int) -> Tag:
    """從資源回收桶還原 Tag。"""
    tag = await db.get(Tag, tag_id)
    if not tag or tag.deleted_at is None:
        raise ValueError(f"Deleted Tag {tag_id} not found")

    tag.deleted_at = None

    # Audit log
    log = TagChangeLog(
        tag_id=tag.tag_id,
        change_type="restore",
        reason="Restore tag from recycle bin",
        changed_by="api",
    )
    db.add(log)

    await db.commit()
    await db.refresh(tag)
    return tag


async def hard_delete_tag(db: AsyncSession, tag_id: int) -> None:
    """徹底抹除 Tag，包含所有 mappings、變更紀錄。"""
    tag = await db.get(Tag, tag_id)
    if not tag or tag.deleted_at is None:
        raise ValueError(f"Deleted Tag {tag_id} not found")

    # 1. 刪除相關 Mapping
    await db.execute(
        TagSourceMapping.__table__.delete().where(TagSourceMapping.tag_id == tag_id)
    )
    # 2. 刪除相關 Change log
    await db.execute(
        TagChangeLog.__table__.delete().where(TagChangeLog.tag_id == tag_id)
    )
    # 3. 不主動刪除 Telemetry 等關聯時序資料 (遵守保留策略與防禦全表掃描)

    await db.delete(tag)
    await db.commit()
