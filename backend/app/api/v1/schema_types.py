"""
Schema Type CRUD API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import SchemaTypeCreate, SchemaTypeUpdate, SchemaTypeOut
from app.services import schema_type_service

router = APIRouter(prefix="/payload-schemas", tags=["Payload Schemas"])


@router.get("/", response_model=list[SchemaTypeOut])
async def list_schema_types(db: AsyncSession = Depends(get_db)):
    """列出所有 Schema Type。"""
    return await schema_type_service.list_schema_types(db)


@router.get("/suggestions", response_model=list[SchemaTypeOut])
async def list_suggestions(db: AsyncSession = Depends(get_db)):
    """列出所有推斷出的 Schema 建議。"""
    return await schema_type_service.list_suggestions(db)


# ─── Recycle Bin ──────────────────────────────────────────────


@router.get("/deleted", response_model=list[SchemaTypeOut])
async def get_deleted_schema_types(db: AsyncSession = Depends(get_db)):
    """取得所有 Soft-deleted 的 Schema Types。"""
    return await schema_type_service.get_deleted_schema_types(db)


@router.put("/{type_id}/restore", response_model=SchemaTypeOut)
async def restore_schema_type(type_id: int, db: AsyncSession = Depends(get_db)):
    """從資源回收桶還原 Schema Type。"""
    try:
        return await schema_type_service.restore_schema_type(db, type_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{type_id}/hard", status_code=204)
async def hard_delete_schema_type(type_id: int, db: AsyncSession = Depends(get_db)):
    """徹底抹除 Schema Type。"""
    try:
        await schema_type_service.hard_delete_schema_type(db, type_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Regular CRUD ─────────────────────────────────────────────



@router.get("/{type_id}", response_model=SchemaTypeOut)
async def get_schema_type(type_id: int, db: AsyncSession = Depends(get_db)):
    """取得單一 Schema Type 定義。"""
    st = await schema_type_service.get_schema_type(db, type_id)
    if not st:
        raise HTTPException(status_code=404, detail=f"Schema Type {type_id} not found")
    return st


@router.post("/", response_model=SchemaTypeOut, status_code=201)
async def create_schema_type(body: SchemaTypeCreate, db: AsyncSession = Depends(get_db)):
    """建立新 Schema Type。"""
    return await schema_type_service.create_schema_type(
        db, **body.model_dump()
    )


@router.put("/{type_id}", response_model=SchemaTypeOut)
async def update_schema_type(
    type_id: int, body: SchemaTypeUpdate, db: AsyncSession = Depends(get_db)
):
    """更新 Schema Type。"""
    try:
        return await schema_type_service.update_schema_type(
            db, type_id, **body.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{type_id}", status_code=204)
async def delete_schema_type(type_id: int, db: AsyncSession = Depends(get_db)):
    """刪除 Schema Type。"""
    try:
        await schema_type_service.delete_schema_type(db, type_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.post("/{type_id}/approve", response_model=SchemaTypeOut)
async def approve_suggestion(type_id: int, db: AsyncSession = Depends(get_db)):
    """核准並轉正一個 Schema 建議。"""
    try:
        return await schema_type_service.approve_suggestion(db, type_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
