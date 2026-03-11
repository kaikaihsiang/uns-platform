import logging
import time
from typing import Dict, Optional, Tuple

from .db_pool import DBPool

logger = logging.getLogger("uns.master_data_cache")

class MasterDataCache:
    """
    Master Data Cache: Stores (code_category, code_value) -> (sub_code_value, label).
    Used by the Pipeline to enrich Status/Alarm/Event records.
    """
    def __init__(self, db_pool: Optional[DBPool] = None):
        self._db_pool = db_pool
        # Mapping: (code_category, code_value) -> dict {sub_code, label, metadata}
        self._cache: Dict[Tuple[str, str], dict] = {}
        self._last_refresh = 0.0
        if db_pool:
            self.refresh()

    def refresh(self, force: bool = False):
        """Reload master data from DB."""
        if not self._db_pool:
            return
            
        now = time.monotonic()
        if not force and (now - self._last_refresh < 5.0):
            return

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT code_category, code_value, sub_code_value, label, metadata
                    FROM master_data_codes
                """)
                rows = cur.fetchall()
                cur.close()
            
            new_cache = {}
            for code_cat, code_val, sub_code, label, metadata in rows:
                key = (code_cat, code_val)
                # We take the first one or prioritize empty sub_code if multiple exist
                if key not in new_cache or sub_code == "":
                    new_cache[key] = {
                        "sub_code": sub_code,
                        "label": label,
                        "metadata": metadata if metadata else {}
                    }
            
            self._cache = new_cache
            self._last_refresh = time.monotonic()
            logger.info("MasterDataCache loaded: %d entries", len(self._cache))
        except Exception as e:
            logger.error("Failed to load master data cache: %s", e)

    def lookup(self, code_category: str, code_value: str) -> Optional[dict]:
        """
        [精確查詢] 已知類別與代碼，取得中繼資料。
        """
        key = (code_category, code_value)
        if key in self._cache:
            return self._cache[key]
            
        if self._db_pool and (time.monotonic() - self._last_refresh > 5.0):
            self.refresh()
            return self._cache.get(key)
            
        return None

    def find_metadata(self, code: Optional[str] = None, sub_code: Optional[str] = None) -> Optional[dict]:
        """
        [語義自發現] 透過代碼或子代碼反查其所屬類別與資訊。
        優先序：
        1. 匹配 (code + sub_code) 的組合
        2. 匹配單一 code
        3. 匹配單一 sub_code
        回傳: {"code_category": str, "sub_code": str, "label": str, "metadata": dict}
        """
        if not code and not sub_code:
            return None

        # 1. 嘗試組合匹配 (最精確)
        if code and sub_code:
            for (cat, val), info in self._cache.items():
                if val == code and info.get("sub_code") == sub_code:
                    return {"code_category": cat, **info}

        # 2. 嘗試單一代碼匹配
        if code:
            for (cat, val), info in self._cache.items():
                if val == code:
                    return {"code_category": cat, **info}

        # 3. 嘗試單一子代碼匹配
        if sub_code:
            for (cat, _val), info in self._cache.items():
                if info.get("sub_code") == sub_code:
                    return {"code_category": cat, **info}

        # 若沒找到且過期，刷新後再找一次
        if self._db_pool and (time.monotonic() - self._last_refresh > 5.0):
            self.refresh()
            return self.find_metadata(code, sub_code)
        
        return None

    def find_by_code(self, code_value: str) -> Optional[dict]:
        """
        [NEW] 逆向搜尋：僅憑代碼尋找其所屬類別與資訊。
        回傳字典包含: {"code_category": str, "sub_code": str, "label": str, "metadata": dict}
        """
        if not code_value:
            return None

        # 優先搜尋目前快取
        for (cat, val), info in self._cache.items():
            if val == code_value:
                return {"code_category": cat, **info}

        # 若找不到且已過冷卻期，重新整理快取再試一次
        if self._db_pool and (time.monotonic() - self._last_refresh > 5.0):
            self.refresh()
            for (cat, val), info in self._cache.items():
                if val == code_value:
                    return {"code_category": cat, **info}
        
        return None
