"""
Tag Registry + CRUD + Query API
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    TagCreate, TagOut, TagDetailOut, TagMappingOut, TagChangeLogOut,
    TagValueOut, TagValuesResponse, TagLatestResponse,
)
from app.services import tag_service

router = APIRouter(prefix="/tags", tags=["Tags"])


# ─── Tag CRUD ─────────────────────────────────────────────────


@router.post("/", response_model=TagOut, status_code=201)
async def create_tag(body: TagCreate, db: AsyncSession = Depends(get_db)):
    """建立 Tag（自動建立 tag_source_mapping）。"""
    tag = await tag_service.create_tag(db, **body.model_dump())
    return tag


@router.get("/{tag_id}/detail", response_model=TagDetailOut)
async def get_tag_detail(tag_id: int, db: AsyncSession = Depends(get_db)):
    """取得 Tag 完整資訊（含 mappings + audit history）。"""
    tag = await tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")

    mappings = await tag_service.get_tag_mappings(db, tag_id)
    history = await tag_service.get_tag_history(db, tag_id)

    return TagDetailOut(
        tag=TagOut.model_validate(tag),
        mappings=[TagMappingOut.model_validate(m) for m in mappings],
        history=[TagChangeLogOut.model_validate(h) for h in history],
    )


# ─── Tag Queries ──────────────────────────────────────────────


@router.get("/{node_path:path}/list", response_model=list[TagOut])
async def list_tags(node_path: str, db: AsyncSession = Depends(get_db)):
    """取得某 node 底下的所有 Tag。"""
    tags = await tag_service.list_tags_by_path(db, node_path)
    return tags


@router.get("/{tag_id}/values", response_model=TagValuesResponse)
async def get_tag_values(
    tag_id: int,
    start: datetime | None = Query(None, alias="from"),
    end: datetime | None = Query(None, alias="to"),
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """查詢 Tag 的歷史時序資料（by tag_id，跨 migration 連續）。"""
    tag = await tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")

    rows = await tag_service.get_tag_values(db, tag_id, start=start, end=end, limit=limit)
    data = [
        TagValueOut(
            time=r.time, value=r.value, value_text=r.value_text, quality=r.quality,
        )
        for r in rows
    ]
    return TagValuesResponse(tag_id=tag_id, tag=TagOut.model_validate(tag), data=data)


@router.get("/{tag_id}/latest", response_model=TagLatestResponse)
async def get_tag_latest(tag_id: int, db: AsyncSession = Depends(get_db)):
    """查詢 Tag 的最新值。"""
    tag = await tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")

    row = await tag_service.get_tag_latest(db, tag_id)
    latest = None
    if row:
        latest = TagValueOut(
            time=row.time, value=row.value, value_text=row.value_text, quality=row.quality,
        )
    return TagLatestResponse(tag_id=tag_id, tag=TagOut.model_validate(tag), latest=latest)


# ─── By-Topic Query (F4 驗收標準 5, 6) ───────────────────────


@router.get("/by-topic/{mqtt_topic:path}/values", response_model=TagValuesResponse)
async def get_values_by_topic(
    mqtt_topic: str,
    start: datetime | None = Query(None, alias="from"),
    end: datetime | None = Query(None, alias="to"),
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """
    用 MQTT topic 查詢歷史資料。
    只回傳該 mapping 有效期間的資料（用舊 topic 查→只有搬遷前的資料）。
    """
    rows = await tag_service.get_values_by_topic(
        db, mqtt_topic, start=start, end=end, limit=limit
    )
    if not rows:
        return TagValuesResponse(tag_id=0, data=[])

    tag_id = rows[0].tag_id
    tag = await tag_service.get_tag(db, tag_id)
    data = [
        TagValueOut(time=r.time, value=r.value, value_text=r.value_text, quality=r.quality)
        for r in rows
    ]
    return TagValuesResponse(
        tag_id=tag_id,
        tag=TagOut.model_validate(tag) if tag else None,
        data=data,
    )
