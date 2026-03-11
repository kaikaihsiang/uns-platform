"""
Schema Type Service — CRUD for Schema Types
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UnsPayloadSchema


async def list_payload_schema(db: AsyncSession) -> list[UnsPayloadSchema]:
    """列出所有 Schema Types（過濾掉已刪除的）。"""
    result = await db.execute(
        select(UnsPayloadSchema)
        .where(UnsPayloadSchema.deleted_at.is_(None))
        .order_by(UnsPayloadSchema.schema_name)
    )
    return list(result.scalars().all())


async def get_payload_schema(db: AsyncSession, type_id: int) -> UnsPayloadSchema | None:
    """取得單一 Schema Type。"""
    return await db.get(UnsPayloadSchema, type_id)


async def create_payload_schema(db: AsyncSession, **kwargs) -> UnsPayloadSchema:
    """建立 Schema Type。"""
    schema_type = UnsPayloadSchema(**kwargs)
    db.add(schema_type)
    await db.commit()
    await db.refresh(schema_type)
    return schema_type


async def update_schema_type(
    db: AsyncSession, type_id: int, **kwargs
) -> UnsPayloadSchema:
    """更新 Schema Type（只更新非 None 的欄位）。"""
    schema_type = await db.get(UnsPayloadSchema, type_id)
    if not schema_type:
        raise ValueError(f"Schema Type {type_id} not found")

    for key, value in kwargs.items():
        if value is not None:
            setattr(schema_type, key, value)

    schema_type.version += 1
    schema_type.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(schema_type)
    return schema_type


async def delete_schema_type(db: AsyncSession, type_id: int) -> UnsPayloadSchema:
    """Soft delete Schema Type。"""
    schema_type = await db.get(UnsPayloadSchema, type_id)
    if not schema_type or schema_type.deleted_at is not None:
        raise ValueError(f"Schema Type {type_id} not found")

    schema_type.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(schema_type)
    return schema_type


# ─── Recycle Bin ──────────────────────────────────────────────


async def get_deleted_payload_schema(db: AsyncSession) -> list[UnsPayloadSchema]:
    """取得所有 Soft-deleted 的 Schema Types。"""
    result = await db.execute(
        select(UnsPayloadSchema)
        .where(UnsPayloadSchema.deleted_at.is_not(None))
        .order_by(UnsPayloadSchema.deleted_at.desc())
    )
    return list(result.scalars().all())


async def restore_payload_schema(db: AsyncSession, type_id: int) -> UnsPayloadSchema:
    """從資源回收桶還原 Schema Type。"""
    schema_type = await db.get(UnsPayloadSchema, type_id)
    if not schema_type or schema_type.deleted_at is None:
        raise ValueError(f"Deleted Schema Type {type_id} not found")

    schema_type.deleted_at = None
    schema_type.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(schema_type)
    return schema_type


async def hard_delete_payload_schema(db: AsyncSession, type_id: int) -> None:
    """徹底刪除 Schema Type，從資料庫中抹除。"""
    schema_type = await db.get(UnsPayloadSchema, type_id)
    if not schema_type or schema_type.deleted_at is None:
        raise ValueError(f"Deleted Schema Type {type_id} not found")

    # Nullify FK references in namespace_nodes before deleting
    from app.models import NamespaceNode
    await db.execute(
        update(NamespaceNode)
        .where(NamespaceNode.schema_id == type_id)
        .values(schema_id=None)
    )

    await db.delete(schema_type)
    await db.commit()

async def list_suggestions(db: AsyncSession) -> list[UnsPayloadSchema]:
    """列出所有建議的 Schema Types。"""
    result = await db.execute(
        select(UnsPayloadSchema).where(UnsPayloadSchema.is_suggested.is_(True)).order_by(UnsPayloadSchema.created_at.desc())
    )
    return list(result.scalars().all())


async def approve_suggestion(db: AsyncSession, type_id: int) -> UnsPayloadSchema:
    """核准建議的 Schema Type。"""
    schema_type = await db.get(UnsPayloadSchema, type_id)
    if not schema_type:
        raise ValueError(f"Suggestion {type_id} not found")

    schema_type.is_suggested = False
    schema_type.status = "confirmed"
    schema_type.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(schema_type)
    return schema_type
