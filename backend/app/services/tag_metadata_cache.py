import logging
import time
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NamespaceNode, Tag, TagSourceMapping, UnsPayloadSchema

logger = logging.getLogger("uns.tag_metadata_cache")

class TagMetadataCache:
    """
    Global Tag Metadata Cache (includes Schema and Tag info).
    Enhanced with category-aware primary column mapping for all UNS data types.
    """
    _instance = None
    
    # Map Category -> Primary Target Column in the database table
    CATEGORY_PRIMARY_MAP = {
        "telemetry": "value",
        "measurement": "value",
        "status": "state_code",
        "alarm": "alarm_code",
        "event": "event_code",
        "metrics": "values"
    }
    
    def __init__(self):
        # tag_id -> {display_name, unit, data_type, category, field_map, target_map}
        self._tag_cache: Dict[int, dict] = {}
        self._last_refresh = 0.0
        self._refresh_interval = 300.0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def refresh_if_needed(self, db: AsyncSession, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last_refresh < self._refresh_interval) and self._tag_cache:
            return

        try:
            stmt = (
                select(
                    Tag.tag_id, 
                    Tag.display_name, 
                    Tag.data_point,
                    Tag.category,
                    Tag.unit.label("tag_unit"),
                    Tag.data_type.label("tag_data_type"),
                    UnsPayloadSchema.fields
                )
                .outerjoin(TagSourceMapping, Tag.tag_id == TagSourceMapping.tag_id)
                .outerjoin(NamespaceNode, TagSourceMapping.mqtt_topic == NamespaceNode.full_path)
                .outerjoin(UnsPayloadSchema, NamespaceNode.schema_id == UnsPayloadSchema.schema_id)
            )
            
            res = await db.execute(stmt)
            new_cache = {}
            
            for row in res.all():
                tag_id, display_name, data_point, category, t_unit, t_dt, fields = row
                cat_lower = category.lower() if category else "unknown"
                
                # 1. Map all fields from Schema
                field_map = {}
                target_map = {} 
                
                if fields:
                    for f in fields:
                        fname = f.get("name")
                        target_col = f.get("target_column")
                        f_meta = {
                            "unit": f.get("unit"),
                            "data_type": f.get("type", "float")
                        }
                        if fname:
                            field_map[fname] = f_meta
                        if target_col:
                            target_map[target_col] = f_meta
                
                # 2. Category-Aware Smart Matching
                # Priority 1: Direct match by data_point
                # Priority 2: Match by primary column of that category (e.g., status -> state_code)
                # Priority 3: Fallback to Tag table defaults
                final_unit = t_unit
                final_dt = t_dt
                
                # Attempt to find metadata in Schema
                matched_meta = field_map.get(data_point)
                if not matched_meta:
                    primary_col = self.CATEGORY_PRIMARY_MAP.get(cat_lower)
                    if primary_col:
                        matched_meta = target_map.get(primary_col)
                
                if matched_meta:
                    final_unit = matched_meta["unit"] or t_unit
                    final_dt = matched_meta["data_type"] or t_dt
                
                new_cache[tag_id] = {
                    "display_name": display_name,
                    "unit": final_unit,
                    "data_type": final_dt,
                    "category": category,
                    "field_map": field_map,
                    "target_map": target_map
                }
            
            self._tag_cache = new_cache
            self._last_refresh = now
            logger.info(f"TagMetadataCache: Refreshed with {len(new_cache)} entries (Full Category Auto-Mapping)")
        except Exception as e:
            logger.error(f"TagMetadataCache: Failed to refresh: {e}")

    async def get_all_meta(self, db: AsyncSession) -> Dict[int, dict]:
        await self.refresh_if_needed(db)
        return self._tag_cache

async def get_tag_metadata_cache() -> TagMetadataCache:
    return TagMetadataCache.get_instance()
