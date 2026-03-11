
import sys
import os
from datetime import datetime, timezone

# 加入專案路徑以引用模組
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data-engine')))

from src.pipeline import Pipeline
from src.schema_matcher import SchemaMatch, FieldDef
from src.field_extractor import FieldExtractor
from src.db_writer import EventRecord

# 模擬 Mock 物件
class MockSchemaMatcher:
    def match(self, topic):
        # 建立一個 Recipe Event Schema
        return SchemaMatch(
            schema_id=100,
            schema_name="Recipe Event Schema",
            decoder="json",
            schema_category="event",
            fields=[
                FieldDef(name="event_code", path="$.data.event_code", type="string", target_column="event_code"),
                FieldDef(name="recipe_id", path="$.data.recipe_id", type="string", target_column="details") # 手動映射到溢位袋
            ],
            persist_mode="db",
            store_raw=False
        )

class MockDBWriter:
    def __init__(self):
        self.records = []
    def add_event(self, record):
        self.records.append(record)
    def add_raw_payload(self, record): pass
    def flush(self): pass

# 1. 初始化 Pipeline 與 Mock 組件
writer = MockDBWriter()
pipeline = Pipeline(
    db_pool=None, # 不連接真實 DB
    schema_matcher=MockSchemaMatcher(),
    db_writer=writer,
    field_extractor=FieldExtractor()
)

# 2. 模擬 MQTT 訊息
topic = "TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Event/Recipe"
payload = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "data": {
        "event_code": "RECIPE_LOADED",
        "recipe_id": "RECP-001",       # 在 Schema 中，映射到 details
        "target_temp": 250,           # 不在 Schema 中，應自動溢位
        "step_time": 60               # 不在 Schema 中，應自動溢位
    }
}
payload_bytes = bytes(__import__('json').dumps(payload), 'utf-8')

print(f"--- 執行驗證場景 ---")
print(f"Topic: {topic}")
print(f"Payload: {payload}")

# 3. 執行 Pipeline 處理
pipeline.process(topic, payload_bytes)

# 4. 檢查結果
if writer.records:
    record = writer.records[0]
    print(f"
--- 驗證結果 ---")
    print(f"Category: Event")
    print(f"Event Code (實體欄位): {record.event_code}")
    print(f"Details (溢位袋內容): {record.details}")
    
    # 驗證點
    assert record.event_code == "RECIPE_LOADED"
    assert "recipe_id" in record.details, "FAILED: 手動映射的 details 遺失"
    assert record.details["recipe_id"] == "RECP-001"
    assert "target_temp" in record.details, "FAILED: 自動捕捉的溢位欄位遺失"
    assert record.details["target_temp"] == 250
    assert "step_time" in record.details, "FAILED: 自動捕捉的溢位欄位遺失"
    
    print(f"
✅ [SUCCESS] 單一溢位出口機制驗證通過！")
    print(f" - 手動映射 (recipe_id) 成功進入 details")
    print(f" - 自動捕捉 (target_temp, step_time) 成功進入 details")
    print(f" - 實體欄位 (event_code) 保持獨立")
else:
    print(f"❌ [FAILED] 未產生任何 Record")
