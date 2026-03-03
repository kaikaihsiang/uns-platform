"""
Schema Type Service — CRUD for Schema Types
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SchemaType


async def list_schema_types(db: AsyncSession) -> list[SchemaType]:
    """列出所有 Schema Types。"""
    result = await db.execute(
        select(SchemaType).order_by(SchemaType.type_name)
    )
    return list(result.scalars().all())


async def get_schema_type(db: AsyncSession, type_id: int) -> SchemaType | None:
    """取得單一 Schema Type。"""
    return await db.get(SchemaType, type_id)


async def create_schema_type(db: AsyncSession, **kwargs) -> SchemaType:
    """建立 Schema Type。"""
    schema_type = SchemaType(**kwargs)
    db.add(schema_type)
    await db.commit()
    await db.refresh(schema_type)
    return schema_type


async def update_schema_type(
    db: AsyncSession, type_id: int, **kwargs
) -> SchemaType:
    """更新 Schema Type（只更新非 None 的欄位）。"""
    schema_type = await db.get(SchemaType, type_id)
    if not schema_type:
        raise ValueError(f"Schema Type {type_id} not found")

    for key, value in kwargs.items():
        if value is not None:
            setattr(schema_type, key, value)

    schema_type.version += 1
    schema_type.updated_at = datetime.now()

    await db.commit()
    await db.refresh(schema_type)
    return schema_type


async def delete_schema_type(db: AsyncSession, type_id: int) -> None:
    """刪除 Schema Type。"""
    schema_type = await db.get(SchemaType, type_id)
    if not schema_type:
        raise ValueError(f"Schema Type {type_id} not found")

    await db.delete(schema_type)
    await db.commit()
