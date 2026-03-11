"""
Schema Type CRUD API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import PayloadSchemaCreate, PayloadSchemaOut, PayloadSchemaUpdate
from app.services import schema_type_service

router = APIRouter(prefix="/payload-schemas", tags=["Payload Schemas"])


@router.get("/", response_model=list[PayloadSchemaOut])
async def list_payload_schema(db: AsyncSession = Depends(get_db)):
    """列出所有 Schema Type。"""
    return await schema_type_service.list_payload_schema(db)


@router.get("/suggestions", response_model=list[PayloadSchemaOut])
async def list_suggestions(db: AsyncSession = Depends(get_db)):
    """列出所有推斷出的 Schema 建議。"""
    return await schema_type_service.list_suggestions(db)


# ─── Recycle Bin ──────────────────────────────────────────────


@router.get("/deleted", response_model=list[PayloadSchemaOut])
async def get_deleted_payload_schema(db: AsyncSession = Depends(get_db)):
    """取得所有 Soft-deleted 的 Schema Types。"""
    return await schema_type_service.get_deleted_payload_schema(db)


@router.put("/{schema_id}/restore", response_model=PayloadSchemaOut)
async def restore_payload_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    """從資源回收桶還原 Schema Type。"""
    try:
        return await schema_type_service.restore_payload_schema(db, schema_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{schema_id}/hard", status_code=204)
async def hard_delete_payload_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    """徹底抹除 Schema Type。"""
    try:
        await schema_type_service.hard_delete_payload_schema(db, schema_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Regular CRUD ─────────────────────────────────────────────



@router.get("/{schema_id}", response_model=PayloadSchemaOut)
async def get_payload_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    """取得單一 Schema Type 定義。"""
    st = await schema_type_service.get_payload_schema(db, schema_id)
    if not st:
        raise HTTPException(status_code=404, detail=f"Schema Type {schema_id} not found")
    return st


@router.post("/", response_model=PayloadSchemaOut, status_code=201)
async def create_payload_schema(body: PayloadSchemaCreate, db: AsyncSession = Depends(get_db)):
    """建立新 Schema Type。"""
    return await schema_type_service.create_payload_schema(
        db, **body.model_dump()
    )


@router.put("/{schema_id}", response_model=PayloadSchemaOut)
async def update_schema_type(
    schema_id: int, body: PayloadSchemaUpdate, db: AsyncSession = Depends(get_db)
):
    """更新 Schema Type。"""
    try:
        return await schema_type_service.update_schema_type(
            db, schema_id, **body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{schema_id}", status_code=204)
async def delete_schema_type(schema_id: int, db: AsyncSession = Depends(get_db)):
    """刪除 Schema Type。"""
    try:
        await schema_type_service.delete_schema_type(db, schema_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.post("/{schema_id}/approve", response_model=PayloadSchemaOut)
async def approve_suggestion(schema_id: int, db: AsyncSession = Depends(get_db)):
    """核准並轉正一個 Schema 建議。"""
    try:
        return await schema_type_service.approve_suggestion(db, schema_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
