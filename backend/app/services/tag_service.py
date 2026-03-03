"""
Tag Service — Tag CRUD, auto mapping, and query
"""
from datetime import datetime

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


async def get_tag(db: AsyncSession, tag_id: int) -> Tag | None:
    """取得單一 Tag。"""
    return await db.get(Tag, tag_id)


async def list_tags_by_path(db: AsyncSession, node_path: str) -> list[Tag]:
    """取得某 asset_path 底下的所有 Tag（含子路徑）。"""
    result = await db.execute(
        select(Tag).where(
            Tag.asset_path.like(f"{node_path}%")
        ).order_by(Tag.asset_path, Tag.category, Tag.data_point)
    )
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
