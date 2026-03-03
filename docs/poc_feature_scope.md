# UNS Platform — PoC Feature Scope

> **目標**：定義 PoC 的 8 個功能邊界與驗收標準。
> 各 Agent 開始工作前必須先讀這份文件，確認「PoC 只做這些」。
> **預計時程**：4-6 週

---

## Feature 1：Namespace Tree 拖拉編輯

| | 說明 |
|---|---|
| **Owner** | Frontend + Backend |
| **價值** | 管理者可以視覺化定義工廠的 ISA-95 階層 |

### ✅ In Scope

- Web UI 顯示 Namespace Tree（Ant Design Tree + dnd-kit）
- 建立 structural node（Enterprise / Site / Area / Line / Equipment）
- 建立 topic node（Telemetry / Status / Event）
- 拖拉移動 node（觸發 Live Migration — 見 Feature 4）
- 重新命名 node
- Soft delete node（標記 deleted_at，不真正刪除）
- Node 類型視覺區分（structural = 📁、topic = 📡）
- Backend API：Namespace CRUD（GET tree / POST create / PUT move / PUT rename / DELETE soft）

### ❌ Out of Scope（MVP）

- 批次匯入 Namespace（CSV/YAML upload）
- Namespace 版本控制 / diff
- 多人同時編輯衝突處理
- Namespace template 套用

### 📋 驗收標準

1. 管理者可在 UI 上建立 3 層以上的 Namespace 結構
2. 可拖拉移動任意 node，移動後 full_path 自動更新
3. 刪除 node 後 UI 不顯示，但 DB 中 deleted_at 有值
4. Backend API 可獨立用 curl/Postman 操作

---

## Feature 2：MQTT → Consumer → TimescaleDB

| | 說明 |
|---|---|
| **Owner** | Data Engine + DB |
| **價值** | 設備 publish MQTT → 資料自動流入 DB，不需要任何人工介入 |

### ✅ In Scope

- Data Engine 啟動後自動訂閱 `#`（所有 topic）
- JSON Decoder（Phase 1 只做 JSON）
- Schema Matcher：topic 有綁定 Schema Type → 用定義好的 rules extract
- Field Extractor：依 Schema Type fields → `(tag_id, value, timestamp)`
- Batch INSERT to `ts_telemetry`（psycopg2 execute_values）
- Raw payload 同時寫入 `ts_raw_payloads`（Dual Storage）
- Deadband 支援（值變化 < 門檻 → 跳過寫入）
- Timestamp 處理：優先 payload 的、fallback 到 receive time

### ❌ Out of Scope（MVP）

- Sparkplug B / text_csv / custom decoder
- Shared subscription load balancing（$share）
- Consumer HA / 自動 failover
- 寫入到 ts_status / ts_events / ts_measurements（PoC 只寫 ts_telemetry + ts_raw）

### 📋 驗收標準

1. 用 `mosquitto_pub` 發一筆 JSON → 30 秒內出現在 ts_telemetry
2. 同一 tag 連續發送 value=25.0 × 10 次（deadband=0.1）→ DB 只寫入 1 筆
3. Raw payload 在 ts_raw_payloads 中可查到
4. Consumer 斷線後自動重連（模擬 EMQX 重啟）

---

## Feature 3：Per-topic Persistence Config

| | 說明 |
|---|---|
| **Owner** | Frontend + Backend + Data Engine |
| **價值** | 管理者可對每個 topic 獨立設定「存/不存/只 retain」 |

### ✅ In Scope

- UI 上選擇 topic node → 設定 persist_mode（db / retain / passthrough）
- UI 上設定 retention_days（預設 90）
- Backend API：PUT /namespace/nodes/{id}/persistence
- Data Engine 讀取 persist_mode 決定是否寫入 DB

### ❌ Out of Scope（MVP）

- Retention policy 自動執行（自動刪除過期資料）— PoC 只設定，不執行
- Compression policy 自動啟用
- UI 上顯示儲存成本估算

### 📋 驗收標準

1. Topic A 設 `db` → 資料寫 DB ✅
2. Topic B 設 `passthrough` → 資料不寫 DB ✅、不 retain
3. Topic C 設 `retain` → EMQX retained message 有值、DB 無資料
4. 切換 persist_mode 後，下一筆資料立即生效

---

## Feature 4：Tag 身份分離 + Live Migration

| | 說明 |
|---|---|
| **Owner** | Backend + DB |
| **價值** | 設備搬家（Line1 → Line2），歷史資料不中斷 — **核心差異化** |

### ✅ In Scope

- `tags` 表：tag_id 永久不變
- `tag_source_mapping` 表：MQTT topic → tag_id，可更新
- 建立 tag 時自動建立 mapping
- 移動 node（Feature 1）→ Migration Engine 自動：
  - 舊 mapping deactivate（is_active = false）
  - 新 mapping 建立（is_active = true）
  - tag.asset_path 更新
  - Audit log 記錄
- 歷史資料用 tag_id 查詢 → 搬遷前後連續

### ❌ Out of Scope（MVP）

- EMQX ACL 自動同步（PoC 不做 ACL）
- 通知 downstream consumer 更新訂閱
- 合併兩個 tag / 拆分 tag
- Migration rollback

### 📋 驗收標準

1. Tag 在 Line1 時寫入 10 筆溫度資料
2. UI 拖拉 node 到 Line2
3. Tag 在 Line2 繼續寫入 10 筆溫度資料
4. 用 tag_id 查歷史 → 完整 20 筆，時間軸連續
5. 用舊 topic 查 → 只有前 10 筆
6. 用新 topic 查 → 只有後 10 筆

---

## Feature 5：歷史查詢 REST API

| | 說明 |
|---|---|
| **Owner** | Backend |
| **價值** | 外部系統可以 HTTP 查詢歷史資料 |

### ✅ In Scope

- `GET /api/v1/namespace/tree` — 完整 Namespace 結構
- `GET /api/v1/tags/{node_path}/list` — 某 node 底下的所有 Tag
- `GET /api/v1/tags/{tag_id}/values?from=&to=` — 歷史時序資料
- `GET /api/v1/tags/{tag_id}/latest` — 最新值
- Response 格式：JSON，含 tag metadata + data points
- OpenAPI / Swagger UI 自動文件

### ❌ Out of Scope（MVP）

- gRPC Query API
- 分頁 / streaming（大量資料）
- 聚合查詢（avg, min, max by interval）
- 資料匯出（CSV / Excel）

### 📋 驗收標準

1. Swagger UI 可看到所有 endpoint
2. GET tree → 回傳完整 Namespace 結構 JSON
3. GET values → 回傳指定時間範圍的資料，含 timestamp + value
4. GET latest → 回傳最新一筆資料

---

## Feature 6：Schema Type Auto-detect

| | 說明 |
|---|---|
| **Owner** | Data Engine + Frontend |
| **價值** | 設備接上來不用手動定義 schema，系統自動偵測 — **demo 亮點** |

### ✅ In Scope

- 收到未綁定 Schema Type 的 topic payload → 進入 auto-detect 模式
- 累積 N 筆（預設 10，PoC 用小數字方便 demo）後產生建議
- 推斷每個 key 的 type（float / string / boolean / json）
- 產生建議的 Schema Type（status = suggested）
- UI 顯示建議，管理者可：確認（confirmed）/ 調整 / 忽略
- 確認後開始 extract + persist

### ❌ Out of Scope（MVP）

- LLM 增強推斷（用 AI 猜 Tag 名稱/單位）
- 自動偵測 timestamp_field
- 偵測 nested JSON / array
- Backfill（確認 Schema Type 後重新掃描 raw payload）

### 📋 驗收標準

1. 發送 10 筆 `{"temp": 25.3, "pressure": 2.1}` 到新 topic
2. UI 顯示 auto-detect 建議：2 fields（temp: float, pressure: float）
3. 管理者點「確認」
4. 後續 payload 開始自動 extract → 出現在 ts_telemetry
5. 管理者可在確認前修改欄位名稱/單位

---

## Feature 7：MCP Server 基本版

| | 說明 |
|---|---|
| **Owner** | Backend |
| **價值** | 讓 LLM Agent 可以查詢工廠資料 — **AI-Ready 的核心** |

### ✅ In Scope

- 獨立 Python process（不內嵌在 Backend）
- MCP Protocol：stdio transport（本機使用）
- 3 個 Tools：
  - `browse_namespace(path)` → 呼叫 Backend REST → 回傳子節點
  - `query_telemetry(tag_id, start, end)` → 呼叫 Backend REST → 回傳資料
  - `get_latest_values(tag_ids[])` → 呼叫 Backend REST → 回傳最新值
- 1 個 Resource：
  - `uns://namespace/tree` → 快取 Namespace 全貌

### ❌ Out of Scope（MVP）

- SSE transport（遠端存取）
- search_tags、query_events、get_production_run tools
- 多 LLM 特化版本
- Auth / API Key 驗證

### 📋 驗收標準

1. Claude Desktop 或 Gemini CLI 可連上 MCP Server
2. LLM 輸入「瀏覽工廠結構」→ 呼叫 browse_namespace → 回傳 Namespace tree
3. LLM 輸入「查詢 Line1 Printer 溫度」→ 自動找到 tag → 呼叫 query_telemetry → 回傳資料
4. MCP Server 的 tool schema 有清楚的 description（LLM 看得懂）

---

## Feature 8：AI Demo

| | 說明 |
|---|---|
| **Owner** | 整合（你 + Backend）|
| **價值** | Demo 最震撼的一幕 — 用人話查工廠資料 |

### ✅ In Scope

- 連接一個外部 LLM（Claude Desktop 或 Gemini）
- 透過 Feature 7 的 MCP Server 查詢
- 準備 Demo 劇本：
  - 「瀏覽工廠結構」→ 顯示 Namespace tree
  - 「查 Line1 Printer 溫度趨勢」→ 找 tag → 查歷史 → 回覆摘要
  - 「Line1 Printer 搬到 Line2 後，溫度有異常嗎？」→ 查遷移前後 → 比較
- Demo 資料準備（模擬設備 publish 溫度/壓力）

### ❌ Out of Scope（MVP）

- 內建 AI Chat UI（在 Namespace Manager 裡的對話框）
- 異常自動診斷
- LLM 增強 Schema detect
- Production Context 相關查詢

### 📋 驗收標準

1. 用自然語言問 3 個問題，LLM 都能正確查到資料並回答
2. 全程不需要人工輸入 SQL、tag_id、time range
3. Demo 可以在 5 分鐘內完成（含準備資料）

---

## PoC 功能依賴關係

```
                    ┌── F6 Auto-detect
                    │
F2 MQTT→DB ─────────┤
                    │
F4 Tag+Migration ───┼── F1 Namespace Tree ── F3 Persistence Config
                    │
F5 REST API ────────┼── F7 MCP Server ── F8 AI Demo
                    │
                    └── (DB Schema 是所有功能的基礎)
```

## 建議開發順序

| 週次 | 功能 | 理由 |
|---|---|---|
| Week 1-2 | DB Schema + F2 (Consumer) + F5 (REST API) | 先讓資料能進能出 |
| Week 2-3 | F1 (Namespace Tree) + F4 (Tag + Migration) | 核心差異化 |
| Week 3-4 | F3 (Persistence) + F6 (Auto-detect) | 管理功能 |
| Week 4-5 | F7 (MCP Server) + F8 (AI Demo) | Demo 亮點 |
| Week 5-6 | 整合測試 + Demo 劇本排練 | 上場準備 |
