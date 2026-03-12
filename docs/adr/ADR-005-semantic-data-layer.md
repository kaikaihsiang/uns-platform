# ADR-005: UNS 語義資料存取層 (Semantic Data Access Layer)

## 狀態
提案中 (Proposed)

## 背景
目前的 UNS 平台已具備資料收集 (Data Engine) 與基礎存儲 (TimescaleDB) 能力。然而，外部系統 (如 AI 診斷、ERP、MES) 若直接存取資料庫或訂閱原始 MQTT Topic，會面臨以下痛點：
1. **語義斷層**：原始數據僅有數值 (如 `1`, `0`)，缺乏工業脈絡 (如 `Running`, `Stopped`)。
2. **路徑耦合**：若 MQTT Topic 因設備遷移而改變，外部系統的整合邏輯會隨之失效。
3. **缺乏生產脈絡**：難以直接查詢「特定批次 (Lot)」或「特定工單 (Order)」的完整性能指標。

## 角色定位 (Platform Persona)
UNS 平台在 Feature 5 之後，定位為 **「工業語義網關 (Industrial Semantic Gateway)」**：
- **Observer/Recorder**: 紀錄現場發生的所有狀態變化。
- **Context Provider**: 為原始數據附加生產、設備、品質維度的元數據。
- **Interface Provider**: 提供標準化、具備語義解釋能力的資料出口。

---

## 介面規格清單 (Interface List)

### 1. 命名空間服務 (Namespace & Metadata Service)
*主要用於管理與探索 UNS 樹狀結構。*

| Interface | Type | 功能描述 | 查詢/過濾方式 |
| :--- | :--- | :--- | :--- |
| `BrowseNodes` | REST/gRPC | 瀏覽 ISA-95 階層 (Site/Area/Line/Equip) | 支援 `parent_path` 過濾，回傳子節點清單。 |
| `GetNodeMetadata` | REST | 取得特定節點的元數據 (Tag ID, Unit, Label) | 透過 `full_path` 或 `tag_id` 查詢。 |
| `SearchTags` | REST/MCP | 模糊搜尋具有特定特徵的標籤 | `filter: { "unit": "degC", "category": "Status" }` |

### 2. 時序數據服務 (UNS Data Service)
*核心高性能出口，整合時序數據與語義轉譯。*

| Interface | Type | 功能描述 | 語義解釋邏輯 |
| :--- | :--- | :--- | :--- |
| `GetLatestSnapshot` | gRPC/REST | 取得一組節點的最新值。 | 自動附加 `semantic_label` (如 `1` -> `Productive`)。 |
| `QueryHistory` | gRPC | 查詢歷史數據。 | 支援 `time_range` + `sampling_interval` (降採樣)。 |
| `QueryBatchData` | gRPC/MCP | 查詢特定生產批次的所有數據。 | **關鍵過濾**：輸入 `run_id` 或 `lot_id`，自動回傳該批次起訖時間內的所有 Tag 數據。 |
| `WatchDataStream` | gRPC (Stream) | 即時訂閱語義路徑的數據變化。 | 外部系統訂閱 `Line1/Equip1/#`，UNS 自動過濾底層所有 Tag 異動。 |

### 3. 工業運算服務 (Industrial Logic Service)
*提供經過計算的關鍵指標 (KPI)。*

| Interface | Type | 功能描述 | 計算依據 |
| :--- | :--- | :--- | :--- |
| `GetOEE` | REST/MCP | 查詢設備在特定時間或批次的 OEE 指標。 | 基於 `ts_status` 的 SEMI E10 狀態累計。 |
| `GetSPCSummary` | REST/MCP | 取得製程能力的統計摘要 (Cpk, Avg, StdDev)。 | 基於 `ts_measurements` 與品質規格界限 (Spec Limits)。 |

---

## 數據利用方式 (Interaction Patterns)

### A. 語義路徑查詢 (Semantic Path Query)
外部系統不應使用資料庫 ID，而是使用語義路徑：
- **Query**: `GET /v1/data/values?path=Enterprise/Site1/Line1/Mixer/Motor/Temperature`
- **Response**: 包含 `value: 85.5`, `unit: "degC"`, `is_alarm: false`。

### B. 狀態轉譯機制 (State Mapping)
UNS 必須內建對應表，將原始設備碼轉譯為 **SEMI E10 標準狀態**：
- `1` -> `PRODUCTIVE` (生產中)
- `2` -> `STANDBY` (待機)
- `3` -> `UNSCHEDULED_DOWN` (非預期停機)
*API 回傳應同時包含 `raw_value` 與 `semantic_state`。*

### C. 生產脈絡綁定 (Batch-Aware Filtering)
當查詢帶入 `run_id` 時，UNS 語義層應執行以下動作：
1. 從 `production_runs` 資料表查找 `start_time` 與 `end_time`。
2. 自動在 `ts_telemetry` 與 `ts_status` 中執行時間過濾。
3. 回傳整合後的「批次數據包」。

---

## MCP Tool 規格建議 (針對 AI Agent)

為了讓 AI 能有效地與 UNS 互動，建議實作以下 MCP 工具：

1. `discover_factory_structure(path)`:
   - Input: 起始路徑 (預設為 `/`)
   - Output: 子節點清單與節點類型 (Structural/Topic)。
2. `get_batch_analysis(lot_id)`:
   - Input: 批次編號。
   - Output: 該批次的 OEE 摘要、最高溫度、警報次數。
3. `find_tags_by_attribute(attribute_query)`:
   - Input: 如 "找尋所有溫度感測器"。
   - Output: 相關的 `full_path` 清單。

## 決策後果
- **優點**: 外部整合極度簡單，AI 診斷不再需要理解底層資料表結構。
- **缺點**: 語義層會增加額外的 CPU 開銷 (轉譯邏輯)，需透過高效快取 (`MasterDataCache`) 補償。
- **影響**: 需要在 Backend 新增 gRPC 服務層，並擴展現有的 REST API 返回結構。
