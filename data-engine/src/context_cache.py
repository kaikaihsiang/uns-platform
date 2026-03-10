import logging
import time
from typing import Dict, Optional
from .db_pool import DBPool

logger = logging.getLogger("uns.context_cache")

class ActiveRunCache:
    """
    In-memory cache for active Production Runs.
    Maps equipment_path -> {'run_id': int, 'lot_id': str}
    Prevents high-frequency telemetry from querying the database.
    """

    def __init__(self, db_pool: Optional[DBPool] = None):
        self._db_pool = db_pool
        # Mapping: equipment_path -> {"run_id": 1, "lot_id": "L123"}
        self._cache: Dict[str, dict] = {}
        self._last_refresh = 0.0
        if self._db_pool:
            self.refresh()

    def refresh(self, force: bool = False):
        """Loads all active runs (status='running') from the database."""
        if not self._db_pool:
            return
            
        now = time.monotonic()
        if not force and (now - self._last_refresh < 5.0):
            return

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT equipment_path, run_id, lot_id 
                    FROM production_run 
                    WHERE status = 'running'
                    """
                )
                rows = cur.fetchall()
                cur.close()

            new_cache = {}
            for row in rows:
                eq_path, run_id, lot_id = row
                new_cache[eq_path] = {"run_id": run_id, "lot_id": lot_id}
            
            self._cache = new_cache
            self._last_refresh = now
            logger.info("ActiveRunCache refreshed. Currently tracking %d active runs.", len(self._cache))
        except Exception as e:
            logger.error("Failed to refresh ActiveRunCache: %s", e)

    def get_active_run(self, equipment_path: Optional[str]) -> Optional[dict]:
        """
        Returns the active run context for a given equipment path.
        If the exact path isn't found, it walks up the path tree 
        (e.g., 'Site/Area/Line/Machine' falls back to 'Site/Area/Line').
        """
        if not equipment_path:
            return None

        parts = equipment_path.split('/')
        while parts:
            current_path = '/'.join(parts)
            if current_path in self._cache:
                return self._cache[current_path]
            parts.pop()
        
        return None
