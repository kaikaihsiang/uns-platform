from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.production import ProductionRun
from app.schemas.production import ProductionRunCreate, ProductionRunUpdate

class ProductionService:
    @staticmethod
    async def create_run(db: AsyncSession, run_in: ProductionRunCreate) -> ProductionRun:
        """
        Create a new production run.
        If an active run exists on the same equipment_path, complete it first.
        """
        # 1. End any currently active runs on this equipment
        await db.execute(
            update(ProductionRun)
            .where(
                ProductionRun.equipment_path == run_in.equipment_path,
                ProductionRun.status == "running"
            )
            .values(
                status="completed", 
                end_time=datetime.now(timezone.utc), 
                result="Auto-closed by new run"
            )
        )
        
        # 2. Create the new run
        db_run = ProductionRun(**run_in.model_dump())
        db.add(db_run)
        await db.commit()
        await db.refresh(db_run)
        return db_run

    @staticmethod
    async def get_active_runs(db: AsyncSession, equipment_path: Optional[str] = None) -> List[ProductionRun]:
        """
        Get all active production runs, optionally filtered by equipment_path prefix.
        """
        stmt = select(ProductionRun).where(ProductionRun.status == "running")
        if equipment_path:
            stmt = stmt.where(ProductionRun.equipment_path.startswith(equipment_path))
            
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search_history_runs(
        db: AsyncSession, 
        equipment_path: Optional[str] = None,
        lot_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[ProductionRun]:
        """
        Search historical production runs with filters.
        """
        stmt = select(ProductionRun)
        if equipment_path:
            stmt = stmt.where(ProductionRun.equipment_path.startswith(equipment_path))
        if lot_id:
            stmt = stmt.where(ProductionRun.lot_id.ilike(f"%{lot_id}%"))
        if start_time:
            stmt = stmt.where(ProductionRun.start_time >= start_time)
        if end_time:
            stmt = stmt.where(ProductionRun.start_time <= end_time)
            
        stmt = stmt.order_by(ProductionRun.start_time.desc())
        
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_run_by_id(db: AsyncSession, run_id: int) -> Optional[ProductionRun]:
        """Get a specific run by ID."""
        result = await db.execute(select(ProductionRun).where(ProductionRun.run_id == run_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_run(db: AsyncSession, run_id: int, run_update: ProductionRunUpdate) -> Optional[ProductionRun]:
        """
        Update an existing production run (e.g., mark as completed).
        """
        db_run = await ProductionService.get_run_by_id(db, run_id)
        if not db_run:
            return None
            
        update_data = run_update.model_dump(exclude_unset=True)
        # If status changes to something other than running and end_time wasn't provided, set it
        if "status" in update_data and update_data["status"] != "running" and "end_time" not in update_data:
             if db_run.end_time is None:
                 update_data["end_time"] = datetime.now(timezone.utc)
                 
        for key, value in update_data.items():
            setattr(db_run, key, value)
            
        await db.commit()
        await db.refresh(db_run)
        return db_run
