from datetime import datetime, timezone
from typing import List, Optional

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

    @staticmethod
    async def get_run_data(db: AsyncSession, run_id: int) -> dict:
        """
        Fetch all time-series data associated with a production run (All 6 categories).
        Includes data filtered by both run_id OR lot_id.
        Enriches data with unit and data_type from TagMetadataCache.
        Smart mapping: Vector unit maps for Metrics, Scalar units for others.
        """
        from sqlalchemy import or_
        from app.models import TsTelemetry, TsStatus, TsAlarms, TsEvents, TsMeasurements, TsMetrics, ProductionRun
        from app.services.tag_metadata_cache import TagMetadataCache
        
        # 0. Fetch the run to get lot_id
        run_res = await db.execute(select(ProductionRun).where(ProductionRun.run_id == run_id))
        run = run_res.scalar_one_or_none()
        if not run:
            return None
            
        lot_id = run.lot_id

        # 1. Get Tag Metadata Cache (Singleton)
        tag_cache_svc = TagMetadataCache.get_instance()
        tag_meta_cache = await tag_cache_svc.get_all_meta(db)

        # Helper to execute and format
        async def fetch_category(model):
            stmt = select(model)
            # Apply expanded filter: (run_id OR lot_id)
            filter_cond = or_(model.run_id == run_id)
            if lot_id:
                filter_cond = or_(model.run_id == run_id, model.lot_id == lot_id)
                
            stmt = stmt.where(filter_cond).order_by(model.time.asc())
            res = await db.execute(stmt)
            
            records = []
            for row in res.scalars().all():
                d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
                
                # Enrich with metadata from central cache
                meta = tag_meta_cache.get(row.tag_id, {})
                d["display_name"] = meta.get("display_name", f"Tag {row.tag_id}")
                
                # 2. Category-Specific Semantic Enrichment
                if model == TsMetrics:
                    # Metrics: unit corresponds to keys in 'values' JSON
                    fmap = meta.get("field_map", {})
                    val_json = d.get("values", {})
                    if isinstance(val_json, dict):
                        d["unit"] = {k: fmap.get(k, {}).get("unit") for k in val_json.keys()}
                        d["data_type"] = {k: fmap.get(k, {}).get("data_type", "float") for k in val_json.keys()}
                    else:
                        d["unit"] = None
                        d["data_type"] = "json"
                else:
                    # Others (Telemetry, Status, etc.): scalar unit describes primary data column
                    d["unit"] = meta.get("unit")
                    d["data_type"] = meta.get("data_type", "float")
                
                records.append(d)
                
            return records

        # Fetch All Categories
        return {
            "telemetry": await fetch_category(TsTelemetry),
            "status": await fetch_category(TsStatus),
            "alarms": await fetch_category(TsAlarms),
            "events": await fetch_category(TsEvents),
            "measurements": await fetch_category(TsMeasurements),
            "metrics": await fetch_category(TsMetrics)
        }
