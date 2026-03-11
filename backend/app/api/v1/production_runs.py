from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.production import ProductionRunCreate, ProductionRunOut, ProductionRunUpdate
from app.services.production_service import ProductionService

router = APIRouter(prefix="/production-runs", tags=["Production Context"])


@router.post("/", response_model=ProductionRunOut, status_code=status.HTTP_201_CREATED)
async def start_production_run(
    run_in: ProductionRunCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    1. Lot Start: Create a new production run state.
    If there is already a running lot on this equipment_path, it will be automatically 
    marked as completed.
    """
    return await ProductionService.create_run(db, run_in)


@router.patch("/{run_id}", response_model=ProductionRunOut)
async def update_production_run(
    run_id: int,
    run_update: ProductionRunUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    2. Lot End/Complete: Update the status of an existing production run.
    (e.g., status="Completed", end_time).
    """
    run = await ProductionService.update_run(db, run_id, run_update)
    if not run:
        raise HTTPException(status_code=404, detail="Production run not found")
    return run


@router.get("/active", response_model=List[ProductionRunOut])
async def get_active_runs(
    equipment_path: Optional[str] = Query(None, description="Prefix path to filter equipment runs"),
    db: AsyncSession = Depends(get_db)
):
    """
    3. Query Active Runs: Get currently active production contexts.
    Can be filtered by equipment_path.
    """
    return await ProductionService.get_active_runs(db, equipment_path)


@router.get("/search", response_model=List[ProductionRunOut])
async def search_history_runs(
    equipment_path: Optional[str] = Query(None, description="Prefix path to filter equipment runs"),
    lot_id: Optional[str] = Query(None, description="Lot ID filter"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    db: AsyncSession = Depends(get_db)
):
    """
    4. Search History Runs: Query historical production contexts.
    """
    return await ProductionService.search_history_runs(db, equipment_path, lot_id, start_time, end_time)
