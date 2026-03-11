"""
UNS Data Engine — Category Router

依照 ADR-001 決策：
1. schema_types.category (如果有設定)
2. Topic 最末段名稱 Fallback (telemetry/status/alarm/event/measurement/metrics)
3. 預設為 telemetry
"""

import logging

from .schema_matcher import SchemaMatch

logger = logging.getLogger("uns.category_router")


class CategoryRouter:
    """
    決定資料的標的類別 (Category)，進而決定寫入哪張 TimescaleDB 資料表。
    """
    
    VALID_CATEGORIES = {
        "telemetry",
        "status",
        "alarm",
        "event",
        "measurement",
        "metrics"
    }

    def resolve(self, schema: SchemaMatch) -> str:
        """
        決定資料類別。
        
        Priority:
        1. schema.category (必有值，預設為 'telemetry')
        2. 如果 schema.category 是預設值 'telemetry'，嘗試從 Topic 最後一段做 fallback，
           以支援未正確設定 category 的舊 Schema 或自動偵測情境。
        """
        
        # 1. 檢查 Schema 是否有明確定義非預設的類別
        if schema.schema_category and schema.schema_category != "telemetry":
            if schema.schema_category in self.VALID_CATEGORIES:
                return schema.schema_category
            else:
                logger.warning(
                    "Invalid category '%s' in schema '%s', falling back", 
                    schema.schema_category, schema.schema_name
                )

        # 2. Topic 命名慣例 Fallback (方案 A)
        # 例如: TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Status -> status
        last_segment = schema.full_path.split("/")[-1].lower()
        if last_segment in self.VALID_CATEGORIES:
            logger.debug(
                "Inferred category '%s' from topic path for %s", 
                last_segment, schema.full_path
            )
            return last_segment

        # 3. 最終預設
        return "telemetry"
