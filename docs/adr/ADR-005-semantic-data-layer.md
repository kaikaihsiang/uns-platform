# ADR-005: UNS 語義資料存取層與外部整合介面 (Semantic Data Access Layer)

## 狀態
提案中 (Proposed)

## 背景與核心挑戰
UNS 作為工廠的 Single Source of Truth (SSoT)，必須提供介面讓外部系統（SCADA, MES, ERP, AI Agent, 邊緣運算）進行數據存取與回饋。
外部系統通常不具備資料庫內部資訊（如 `tag_id`, `run_id`），其唯一的導航依據是 **語義路徑 (Semantic Path / MQTT Topic Tree)**。
本 ADR 旨在定義一套高泛化、低耦合的介面規格，支援語義化查詢與寫回，並能包容多元的數據類型（Telemetry, Status, Measurement, Metric）。

---

## 1. 應用情境窮舉與分類 (Scenario Classification)

### A. 即時可視化與監控 (Real-time Visualization & Monitoring)
*   **情境 A1 [SCADA/Dashboard 初始化]**：UI 畫面開啟時，需要一次性拉取某條產線（Line）下所有設備目前的最新狀態、遙測數值與警報，以繪製畫面。
*   **情境 A2 [跨系統狀態同步]**：MES 系統需要知道「設備目前是否正在運轉」，以決定是否下發新的生產工單 (Command) 或更新排程進度。

### B. 脈絡導向分析與 AI 診斷 (Context-Aware Analysis & AI Reasoning)
*   **情境 B1 [AI 根本原因分析 (RCA)]**：當發生 `Motor_Overheat` 警報時，AI 系統需要拉取「該警報發生前 10 分鐘到後 5 分鐘」該設備**所有**感測器的歷史趨勢，進行關聯分析。
*   **情境 B2 [批次/工單品質履歷]**：產品完工時 (Lot End)，品質系統需自動抓取「該批次生產期間 (Run ID)」的平均溫度、壓力峰值，以及設備是否有發生過異常停機。

### C. 結構探索與動態綁定 (Dynamic Discovery & Binding)
*   **情境 C1 [動態報表生成]**：使用者想要拉一張報表看全廠的能耗，系統需要先「尋找 (Search)」Namespace 中所有單位為 `kWh` 且標籤包含 `Power` 的 Tag。
*   **情境 C2 [設備搬遷/重組適應]**：當設備從 Line 1 移到 Line 2，外部系統不需修改程式碼，僅透過語義路徑即可無縫繼續存取新位置的數據。

### D. 外部回饋與數據注入 (External Feedback & Data Injection)
*   **情境 D1 [SPC 運算回寫]**：邊緣端的微服務計算出製程能力指標 (Cpk)，或發現 Out of Spec (OOS)，需要將結果依語義路徑寫回 UNS 成為一個「虛擬事件」，供警報系統訂閱。
*   **情境 D2 [AI 健康度評分]**：AI 定期計算設備健康度 (Health Score 0-100)，需要將此指標「寫入」UNS 的特定設備節點下。

### E. 品質檢測與指標監控 (Quality & Metric Monitoring)
*   **情境 E1 [品質儀表板]**：查詢檢測值（Measurement）時，需同時取得 USL/LSL 等規格界限資訊。
*   **情境 E2 [能源績效管理]**：彙整全廠電表數據，計算特定時段的能耗指標 (Metrics)。

---

## 2. 價值排序與實作策略 (Value Ranking & Strategy)

針對上述情境，我們進行價值 (Business Value) 與實作風險 (Implementation Risk) 的評估：

| 優先序 | 類別 | 情議 | 商業價值 | 實作策略 |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | A, E | **多節點最新狀態快照 (Snapshot)** | 極高 (看版剛需) | 支援 Wildcard 的高速查詢介面，整合 `metadata`。 |
| **P0** | B, E | **脈絡導向歷史查詢 (History)** | 極高 (AI/RCA 剛需) | 整合 `run_id` 與時間窗 (Time Range)，提供統一歷史出口。 |
| **P1** | C | **語義與元數據搜尋 (Search)** | 高 (降低整合成本) | 透過屬性 (Attributes/Tags) 反查 Node 結構。 |
| **P1** | D | **語義數據寫回 (PublishData)** | 高 (完成閉環分析) | 支援透過「語義路徑」寫入，自動映射底層標籤。 |

---

## 3. 外部整合架構模式 (Integration Architecture)

為了確保邏輯的一致性與開發效率，我們不進行重複實作，而是採用 **「gRPC-First, REST-Mapped」** 的策略：

### A. 核心實作層 (gRPC Service)
*   所有語義邏輯（路徑反查、狀態轉譯、脈絡對齊）皆在 gRPC `UNSDataService` 中實作。
*   這是平台的「單一邏輯來源 (Single Source of Logic)」。

### B. 自動映射層 (REST/HTTP Gateway)
*   透過 FastAPI 或代理機制，將 gRPC 方法自動映射為 REST Endpoints。
*   **優點**：確保兩套協議看到的資料與邏輯完全一致，SI 可依其技術棧選擇 protocol，而不用擔心計算結果有差異。

---

## 4. 核心數據結構：多型語義數據點 (SemanticDataPoint)

```protobuf
// 此定義為 gRPC 與 REST 共用的數據契約
message SemanticDataPoint {
  string path = 1;                 // 絕對語義路徑 (唯一地址)
  string tag_id = 2;               // 永久內部 ID
  google.protobuf.Timestamp ts = 3; 

  google.protobuf.Value raw_value = 4; // 多型數值 (float, int, string, json)
  string semantic_label = 5;       // 語義轉譯 (e.g., "PRODUCTIVE")
  string unit = 6;                 

  // 擴展元數據 (支撐 Measurement/Metric 特定屬性)
  map<string, string> metadata = 7; 
  string current_run_id = 8;
}
```

---

## 🚨 跨 Agent 會勘點 (Cross-Agent Review Checkpoints)
> 以下為針對初期規格與現有系統（DB Schema、Data Engine 唯一寫入權）摩擦點的修正提案。在進入實作前，需由 **Domain Expert**, **DB Schema Engineer**, **Backend Engineer**, **Data Engine Engineer** 共同會勘確認。

### 1. 寫回機制修正 (回歸 MQTT-First)
*   **原定設計**：`PublishData` 直接寫入 TimescaleDB 並同步觸發 MQTT 事件。
*   **問題**：違反了 `PROGRESS.md` 中「Data Engine 是平台上唯一且專屬負責寫入時間序列資料庫的元件」之鐵律，並可能造成雙重寫入 (Dual Write) 的資料不一致風險。
*   **修正提案**：`PublishData` (gRPC/REST) 僅作為**語義轉譯器 (Semantic Resolver)**。它負責將 `path` 反查為 `mqtt_topic`，並將資料發佈至 EMQX。後續的資料庫寫入統一交由 Data Engine 的 `CategoryRouter` 與 `DBWriter` 處理。

### 2. Snapshot 效能優化 (新增 `latest_values` 快照表)
*   **原定設計**：`GetSnapshot` 需即時查詢最新狀態。
*   **問題**：目前資料依類別分散在 `ts_telemetry`, `ts_status`, `ts_alarms`, `ts_events`, `ts_metrics` 等多張超表。若要撈取整條產線所有設備的最新狀態，需進行極其耗效能的跨表 `UNION` 與 `ORDER BY time DESC LIMIT 1` 操作。
*   **修正提案**：由 **DB Schema Engineer** 規劃新增一張 **`latest_values` 快照表**。由 **Data Engine Engineer** 調整 `DBWriter`，在每次批次寫入時同步執行 `UPSERT`。`GetSnapshot` 即可退化為極速的 $O(1)$ 查詢。

#### `latest_values` 快照表 Schema (第 2 版：JSONB 驅動)

```sql
CREATE TABLE latest_values (
    tag_id          INTEGER PRIMARY KEY REFERENCES tags(tag_id),
    time            TIMESTAMPTZ NOT NULL,
    category        TEXT NOT NULL,
    display_value   TEXT,
    data            JSONB NOT NULL,
    quality         TEXT DEFAULT 'good',
    run_id          INTEGER,
    metadata        JSONB
);
```

**設計考量**：
*   **`data` (JSONB)**: 核心改動。儲存完整解析後的 Record 物件，確保語義不遺失。
*   **`display_value` (TEXT)**: 預先格式化的易讀字串，供 UI 直接顯示，由 Data Engine 在寫入時生成。
*   **`run_id` (INTEGER)**: 獨立欄位並建立索引，用於高速過濾特定生產批次的設備快照。
*   **`metadata` (JSONB)**: 儲存與該時間點相關的動態上下文，如 SPC 上下限。

### 3. 語義搜尋的資料來源 (擴充 `tags.metadata`)
*   **原定設計**：`SearchNamespace` 透過屬性反查路徑（例如：搜尋特定供應商的設備）。
*   **問題**：目前的 `tags` 表與 `schema_types` 表缺乏儲存自定義、靜態元數據（如 vendor, criticality, installation_date）的欄位。
*   **修正提案**：由 **DB Schema Engineer** 在 `tags` 表中新增 `metadata JSONB` 欄位。這將使系統能利用 PostgreSQL 強大的 JSONB 查詢能力，支援複雜的語義反查情境。

### 4. `display_value` 規格定義
為了提供 UI/AI 一致且易讀的摘要，`display_value` 欄位由 Data Engine 根據 `category` 進行預先格式化。

| Schema Category | `data` 欄位關鍵資訊 | `display_value` 生成邏輯與範例 |
| :--- | :--- | :--- |
| **Telemetry** | `value`, `unit` | 將數值格式化到小數點後 2 位，並附上單位。**範例：** `"25.56 °C"` |
| **Status** | `state`, `sub_state`, `mode` | 組合主/子狀態與模式。**範例：** `"PRD (RUN) - Auto"` 或 `"UDT (E-VAC-LOSS)"` |
| **Alarm** | `status`, `severity`, `code` | 組合狀態、嚴重性與告警碼。**範例：** `"Active - Critical (E-VAC-001)"` |
| **Event** | `code`, `result` | 組合事件碼與結果。**範例：** `"LOT_START"` 或 `"RECIPE_DOWNLOAD (Failed)"` |
| **Metrics** | `code`, `values` | 顯示指標碼與核心 OEE 指標。**範例：** `"OEE (A:92, P:96, Q:99)"` |
| **Measurement** | `value`, `unit`, `result` | 顯示量測值、單位與判定結果。**範例：** `"12.51 mm (Pass)"` |

| **Measurement** | `value`, `unit`, `result` | 顯示量測值、單位與判定結果。**範例：** `"12.51 mm (Pass)"` |

### 5. `metadata` 規格定義 (高價值動態上下文)
`latest_values.metadata` 欄位的核心價值在於將「時間點的狀態」與「該時間點的『上下文』」綁定，讓每一筆快照都成為一個自包含的、可供決策的資訊單元。

| Category | 應儲存的 `metadata` (What) | 資訊來源 (Who) | 應用案例 (How) |
| :--- | :--- | :--- | :--- |
| **Telemetry** | `{"lsl": 20.0, "usl": 80.0, "target": 50.0}` (規格上下限) | `Context Cache` (來自 MES 的 Recipe 或 Master Data) | **即時 SPC 預警**：AI Agent 一看到 `value` (25.5) 和 `usl` (80.0) 就能判斷是否在規格內，無需二次查詢 MES。 |
| **Status** | `{"next_state": "RUNNING", "next_mode": "AUTO"}` (預期下個狀態) | `MES/EAP` (透過 Event Payload 提供) | **預測性調度**：上層系統知道設備即將進入生產，可提前準備物料或調度 AGV。 |
| **Alarm** | `{"acknowledge_by": "user123", "root_cause_suggestion": "Cooling_Fan_Failure"}` | `操作員/AI Agent` (透過 `PublishData` 寫回) | **知識庫積累**：AI 可學習「當 Cooling Fan 轉速下降時，通常會伴隨此告警」，建立因果模型。 |
| **Event** | `{"source_system": "MES_01", "correlation_id": "uuid-xyz"}` | `外部系統` (發布 Event 時的 Payload) | **跨系統追蹤**：當出現問題時，可憑 `correlation_id` 追蹤從 ERP -> MES -> UNS 的完整數據鏈路。 |
| **Metrics** | `{"weight": 0.8, "target": 85.0}` (OEE 指標權重與目標) | `Master Data` | **動態 KPI 計算**：營運儀表板可根據不同產線的權重與目標，動態計算加權後的綜合 KPI。 |
| **Measurement**| `{"instrument_id": "Caliper-04", "inspector": "QA-007"}` (量測儀器/人員) | `檢測設備/人員` (發布時的 Payload) | **量測系統分析 (MSA)**：當發現量測數據異常時，可快速追溯到是哪台儀器或哪位檢驗員，判斷問題根源。 |

---

## 6. 介面規格與實作邏輯 (gRPC-First)

### 介面 1：`GetSnapshot` (核心：gRPC)
*   **功能**：取得多路徑最新切片。
*   **REST 映射**：`GET /v1/semantic/snapshot?paths=...`
*   **邏輯**：後端直接查詢 `latest_values` 快照表，一次性撈取所有符合 Wildcard 的路徑。

### 介面 2：`QueryHistory` (核心：gRPC Stream)
*   **功能**：按時間或 `run_id` 拉取歷史串流。
*   **REST 映射**：`GET /v1/semantic/history?run_id=...` (轉換為分頁 JSON)
*   **邏輯**：自動尋找生產脈絡時間軸，並依據 Tag 的 Category 查詢對應的 `ts_*` 超表。

### 介面 3：`SearchNamespace` (核心：gRPC)
*   **功能**：屬性反查路徑。
*   **REST 映射**：`GET /v1/semantic/search?attribute=...`
*   **邏輯**：透過查詢 `tags.metadata` JSONB 欄位反查。

### 介面 4：`PublishData` (核心：gRPC)
*   **功能**：外部系統透過語義路徑寫回數據。
*   **REST 映射**：`POST /v1/semantic/publish`
*   **邏輯**：
    1. 透過 `NamespaceCache` 反查路徑對應的 MQTT Topic。
    2. 若路徑為新定義之指標，則動態向標籤註冊表 (Tag Registry) 申請 ID 與新 Topic。
    3. **將資料發佈 (Publish) 至 MQTT Broker**，結束 API 請求。
    4. (後台非同步) Data Engine 接收 MQTT 訊息並寫入資料庫。


## 決策後果
*   **優點**: 外部系統完全不需理解底層資料庫 ID，實現「路徑即語義」的解耦整合。
*   **缺點**: 每次透過路徑存取皆需進行 ID 轉換，對快取效能有較高要求。
