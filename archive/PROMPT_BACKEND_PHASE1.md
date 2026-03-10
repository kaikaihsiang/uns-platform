# Backend Agent Task: Phase 1 - Target Column Mapping (ADR-003)

## 背景與目標 (Context)
請參考最近建立的架構決策紀錄 `docs/adr/ADR-003-target-column-mapping.md`。
為了解決 L0~L4 異質系統 Payload 欄位不固定的問題，我們決定在 UNS Platform 導入 **Target Column Mapping** 機制。
這允許使用者在定義 `SchemaType` 時，指定 JSONPath 抓出來的數值要寫入目標資料表（如 `ts_alarms`）的哪個具體欄位（如 `severity`）。若未指定，且該資料屬於非 telemetry 類別，則統一收集打包存入該資料表的 `details` (JSONB) 欄位中。

## 你的任務範圍：Phase 1 - Database & Backend Foundation
你的目標是為這個新架構打好資料庫與後端 API 的基礎。這些變更完成後，Data Engine Agent 才能接手後續的資料流轉重構。

### 具體工作項目 (Action Items)

#### 1. DB Schema 更新 (TimescaleDB)
- **目標檔案**：檢視 `docker/init-db/03_timeseries.sql` (或其他負責建立時序表的 SQL 腳本)。
- **任務**：確認或新增 `details` (資料型態為 `JSONB`) 欄位到以下目標資料表：
  - `ts_status`
  - `ts_alarms`
  - `ts_events`
  - `ts_measurements`
- **注意**：`ts_telemetry` **不需要** 加 `details` 欄位（它只處理純數值）。

#### 2. 後端 Pydantic Models 更新 (FastAPI)
- **目標檔案**：`backend/app/schemas/__init__.py` 或負責定義 Schema Type 的 schema 檔案。
- **任務**：找到定義 Schema Type `fields` 的 Pydantic Model (應該包含 `name`, `path`, `type`, `unit`, `extract`, `persist`, `deadband`, `array_mode` 等屬性)。
- **修改**：在這個欄位定義模型中，新增一個可選屬性：
  - `target_column: Optional[str] = None`
- 同時請確認 `SchemaTypeCreate`, `SchemaTypeUpdate`, `SchemaTypeOut` 等模型都能正確接收與輸出這個新屬性。

#### 3. 測試與驗證 (Testing)
- 啟動 Backend 服務與資料庫。
- 透過呼叫 FastAPI 的 POST `/api/v1/schema-types/` 端點，嘗試建立一筆帶有 `target_column` 屬性的 Schema Type。
- 驗證 GET `/api/v1/schema-types/` 能夠正確讀出剛存進去的 `target_column` 值。
- **注意**：因為 SchemaType 的 `fields` 在 DB 中大多是定義為 `JSONB` 欄位（請參考 `docker/init-db/02_namespace.sql`），通常只要 Pydantic model 更新了，FastAPI 寫入 DB 時就會自動把這個新屬性 serialize 成 JSON 存進去。請確認這個機制運作正常。

## 執行與回報規範
1. 執行過程中如果遇到任何因重構造成的 Type Error，請一併修正。
2. 完成後，請更新專案根目錄下的 `TODO_ADR_003_Tasks.md`，將 Phase 1 的項目打勾 `[x]`。
3. 如果有任何阻礙或模糊的地帶，請主動查閱 `docs/platform_system_spec.md` 中的 §12 與 §13 節，或向使用者確認。

---
**請直接開始執行以上任務。**
