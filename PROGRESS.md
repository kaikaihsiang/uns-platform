# UNS Platform — Development Progress Board

> **規則：每個 Agent 對話開始工作前必須讀取此檔案，完成一個段落後必須更新。**

---

## �️ Agent Collaboration & Architecture Contract
⚠️ **所有 Agent 加入開發前，請務必遵守以下架構邊界，嚴禁抄捷徑：**

1. **職責分離 (Separation of Concerns)**：
   - **Backend API (`FastAPI`)**：負責對 Frontend 提供 REST 介面、CRUD 設定 (Namespace, Tags, Schema)。**如果收到設備資料 (Data Write API)，必須 Publish 到 MQTT Broker，絕對不可以繞過 MQTT 寫入資料庫。**
   - **Data Engine (`data-engine`)**：平台上**唯一**且**專屬**負責寫入時間序列資料庫 (`ts_telemetry`, `ts_raw_payloads`) 的元件。它只聽 MQTT Broker，不做其他事。
2. **信任既有文件與實作**：
   - 開發前請必讀 `docs/platform_system_spec.md` 確認欄位定義。
   - `docker-compose.yml` 定義了標準連線端點，各個服務都要從這裡面找對應的 host/port (預設 `localhost` for local dev)。
3. **改動必須知會/註記**：
   - 任何涉及共用資料表 (如 Schema Types) 的增刪改，必須記錄到本檔案或 `schemas/*.sql`。

---

## �🔵 Scaffolding

| 項目 | 狀態 | 完成時間 | 備註 |
|---|---|---|---|
| docker-compose.yml | ✅ DONE | 2026-03-03 | EMQX 5.8.6 + TimescaleDB PG16 (infra only) |
| .env.example | ✅ DONE | 2026-03-03 | |
| DB Schema init | ✅ DONE | 2026-03-03 | docker/init-db/ 5個SQL，自動初始化 |
| Backend project init | ✅ DONE | 2026-03-03 | FastAPI + venv + 13 placeholder endpoints |
| Frontend project init | ✅ DONE | 2026-03-04 | Vite + React + AntD + Zustand, dark industrial theme |
| Data Engine init | ✅ DONE | 2026-03-03 | venv, gmqtt, db_writer 批次寫入機制 |

## 🟢 Feature Development

| Feature | 狀態 | Owner 對話 | 完成時間 | 備註 |
|---|---|---|---|---|
| F1: Namespace Tree 拖拉 | ✅ DONE | frontend-agent | 2026-03-04 | AntD Tree draggable + CRUD modals + detail panel，E2E 驗證通過 |
| F2: MQTT → Consumer → DB | ✅ DONE | data-engine-agent | 2026-03-03 | Backend data API 已完成，Data Engine Pipeline (Decoder/SchemaMatcher/Deadband/DBWriter) 開發完成並通過整合測試 |
| F3: Per-topic Persistence | ✅ DONE | antigravity | 2026-03-04 | 前端已實作 Tree node indicator 圓點及詳細資料面板持久化選項，與 persist_mode API 整合測試完成 |
| F4: Tag + Live Migration | ✅ DONE | backend-engineer | 2026-03-03 | Tag CRUD + auto mapping + migration audit |
| F5: REST API | ✅ DONE | backend-engineer | 2026-03-03 | 13+ endpoints |
| F6: Schema Auto-detect | ✅ DONE | antigravity | 2026-03-04 | AutoDetector 推斷邏輯、Backend 轉正 API 與 Frontend「Schema 建議」管理介面完整實作並驗證通過 |
| F7: MCP Server | ✅ DONE | backend-engineer | 2026-03-03 | 3 tools + 1 resource |
| F8: AI Demo | ✅ DONE | antigravity | 2026-03-04 | 內嵌 AI Chat Panel (Gemini + MCP) 與實作 System Settings Dashboard |
| F10: Recycle Bin | ✅ DONE | antigravity | 2026-03-04 | 3-Tab UI (Nodes/Schemas/Tags) + Store + 還原/永久刪除，前端驗證通過 |
| F11: Data Category UI | ✅ DONE | frontend-agent | 2026-03-05 | Schema/Tag 支援類別、Target Column 動態映射 (ADR-003 Phase 3) 完畢 |
| F11: Data Category Backend | ✅ DONE | data-engine-agent | 2026-03-04 | Data Engine 實作 `CategoryRouter` 與 `DBWriter` 多表寫入且驗證完成 |
| F1 (Phase 2): Production Context | ✅ DONE | back-data-collab | 2026-03-06 | Backend 提供 API + Data Engine 完成自動附加與驗證 |
| F2 (Phase 2): Timeseries ORM | ✅ DONE | backend-engineer | 2026-03-06 | 補齊所有 `ts_*` 表 Model，確保與 ADR-003 分流架構 100% 對齊 |
| F3 (Phase 2): Frontend Phase 3 | ✅ DONE | frontend-agent | 2026-03-06 | Active Lot 看板 + Target Column Mapping UI + Run History (API 404/500 已修復) |
| F4 (Phase 2): Ops Scripts | ✅ DONE | backend-engineer | 2026-03-06 | 實作一鍵啟動 (`start_all.sh`) 與一鍵關閉 (`stop_all.sh`) 提升維運體驗 |
| F4 (Phase 3): DevOps | 🔨 IN PROGRESS | gemini-cli | 2026-03-11 | 基礎設施與 14+ 測試案例已驗證通過 (本地)，CI Workflow 已建立但待遠端觸發驗證 |
| F5 (Phase 2): Data Engine Test Arsenal | ✅ DONE | data-engine-engineer | 2026-03-06 | 實作 `reset_db.sh`、`seed_namespace.sh` (TaiwanPrecision) 與智慧工廠模擬器 (`start_sim.sh`) |

## 🔴 Blockers / Decisions Needed

<!-- 任何 Agent 遇到需要跨對話討論的問題，記在這裡 -->

_（目前無）_

### Architecture Decision Records (ADR) Reference

| ADR | 標題 | 狀態 | 影響元件 |
|---|---|---|---|
| [ADR-001](docs/adr/ADR-001-data-category-routing.md) | Data Category 路由機制 — Schema category + Topic fallback | ✅ Accepted | Data Engine, Schema Types, DBWriter |

> [!IMPORTANT]
> **所有 Agent 在修改 Data Engine Pipeline 或 Schema Types 時，必須先讀完 ADR-001。**
> 實作路由邏輯時需使用 `CategoryRouter` 抽象層，為未來 Node 級別覆蓋保留空間。
### Handover: Target Column Mapping (Backend → Data Engine → Frontend)
**狀態：✅ ALL DONE (2026-03-05, 前後端動態映射功能全數實作)**

- **Phase 1 (Backend)**: 已完成 DB Schema 擴充與 Pydantic Model 支援。
- **Phase 2 (Data Engine)**: 已完成資料管道的動態轉發邏輯。
- **Phase 3 (Frontend)**: 已完成 `SchemaManagement.tsx` 的動態映射 UI 與 `TagsOverview.tsx` 的編輯/刪除功能。
詳見：👉 **[docs/handover/HANDOVER_SCHEMA_MAPPING.md](docs/handover/HANDOVER_SCHEMA_MAPPING.md)**

### Handover: Data Category Routing (Data Engine → Frontend Agent)
**狀態：✅ ALL DONE (2026-03-04, 前後端功能全數實作)**

資料類別分流 (Data Category Routing) 已完成：
- **Backend**: Data Engine 根據 `category` 路由至 `ts_telemetry`, `ts_status`, `ts_alarms` 等。
- **Frontend**: Schema 管理支援類別設定、核准建議時可選擇類別，且 Tag 列表已揭露資料分類。
詳見：👉 **[docs/data_category_routing_plan.md](docs/data_category_routing_plan.md)**

**Backend Agent 任務摘要：**
1. `schema_types` 資料表新增 `category` 欄位。
2. 確認並建立各類別目標表（`ts_status`, `ts_alarms`, ...）。
3. 更新 Schema Types CRUD API 支援 `category` 參數與驗證。
4. 建立各類別的範例 Schema 供後續驗證。

### Handover: System Settings APIs (Frontend → Backend Agent)
**狀態：✅ ALL DONE (2026-03-04, Backend Agent 實作並驗證完畢)**

Frontend 即將實作 System Settings Read-only Dashboard，需要以下 API：

| Method | Path | 說明 | 優先級 |
|---|---|---|---|
| GET | `/api/v1/system/info` | 平台版本、Backend/DB/EMQX/DataEngine 連線狀態、uptime | P0 |
| GET | `/api/v1/system/mqtt-stats` | EMQX 統計快照（proxy 轉發 EMQX REST API `http://localhost:18083/api/v5/stats`） | P1 |
| WebSocket | `/api/v1/system/mqtt-stats/ws` | 每 5 秒推送 EMQX 統計更新（connected_clients, topics, subscriptions, messages/s） | P1 |
| GET | `/api/v1/system/retention` | 各 hypertable (ts_telemetry, ts_events 等) 的 retention period 與 compression 設定 | P2 |
| PUT | `/api/v1/system/retention` | 更新 retention 設定（Phase 2，可先 stub 回 501） | P2 |

### Handover: AI Chat API (Frontend → Backend Agent)
**狀態：✅ DONE (2026-03-04, Backend Agent 實作並驗證完畢 — Mock 模式，待設定 gemini_api_key 後自動切換 Gemini)**

Frontend 即將實作 F8 AI Chat Panel (`/ai-assistant`)。架構決策：
- **LLM**: Gemini 優先（`google-genai` SDK），架構預留 OpenAI 切換
- **MCP**: In-process import `mcp-server/server.py` 中的函式（不走 subprocess）
- **環境變數**: 需在 `.env` 新增 `gemini_api_key`

| Method | Path | 說明 | 優先級 |
|---|---|---|---|
| POST | `/api/v1/ai/chat` | Body: `{message: str, history: [{role, content}]}` → 呼叫 Gemini + MCP tools → 回傳 `{reply: str, tools_used: [{name, args, result}]}` | **P0** |
| (選配) | SSE variant | 串流回覆，header `Accept: text/event-stream` → Server-Sent Events 逐 token 回傳 | P1 |

### Handover: Recycle Bin APIs (Frontend → Backend Agent)
Frontend 即將實作 Recycle Bin 管理介面 (Feature 10)，需要 Backend Agent 協助補齊 API，以便前台串接。目前狀態為 **✅ ALL DONE** (Namespace Nodes / Schema Types / Tags 三類資源的 Recycle Bin API 均已實作並驗證完畢)。

### Bug: Hard Delete API Returns 500
**狀態：✅ RESOLVED (2026-03-04, Backend Agent 修復)**

`DELETE /api/v1/schema-types/{id}/hard` 原先返回 500，根因為 FK 約束違反。Backend Agent 已修復（先清除 `namespace_nodes.schema_type_id` 再刪除）。Frontend 驗證通過 (HTTP 204)。

## 📐 Architecture Decision Records (ADR)

### ADR-001: PoC 階段採用 Mock Auth 策略（2026-03-04）

**決策**：PoC 階段不實作完整 IAM（登入畫面、JWT 發放、角色管理 CRUD），但架構上必須預留介入點。

**理由**：
- 核心目標是驗證 UNS 資料流（MQTT → Tree → Live Migration），過早捲入 IAM 會拖慢時程 20-30%。
- 客戶最終通常要求介接其現有的 AD/Entra ID 或 OIDC，現在自刻 CRUD 只是浪費時間。

**具體做法**：

| 層級 | 做法 | 未來切換 |
|---|---|---|
| **Frontend** | `api/client.ts` Axios Interceptor 硬編碼 `Authorization: Bearer mock-token-admin`；Zustand `useAuthStore` 寫死 `{ name: "Admin", role: "admin" }` | 替換 Token 來源為 OIDC Provider |
| **Backend (FastAPI)** | 所有 endpoints 加 `Depends(get_current_user)`，目前永遠回傳假 Admin 物件，不拋 401/403 | 實作真正 JWT 驗證邏輯 |
| **EMQX / TimescaleDB** | 維持 docker-compose 內部靜態帳號密碼 | 接入 LDAP 或 X.509 |

**效果**：語意與介面約定已卡好，未來切換到正式 SSO 時，只需改 Mock 實作，商業邏輯 Zero Refactoring。

### ADR-002: Enterprise Payload Schema Design & Edge Cases（2026-03-04）

**決策**：在 PoC 階段，Data Engine 的 Schema 實作涵蓋 `SMT_Printer_Telemetry` 以及 4 大類 Event Schemas (`Process`, `Recipe`, `Lot`, `Quality`) 的完整解析能力 (`extract`, `persist`, `deadband`, `array_mode`)。

**理由**：
- 高度靈活的 JSON 解析與陣列支援，可覆蓋 F&B 與 CDMO 產業 80% 以上的主力需求。
- 為確保高效單一 Topic 對應單一資產原則，這 5 類結構已足以支援後續 AI Agent 的查詢與分析 (OEE & 批次追溯)。

**特殊情境 (Edge Cases) 與未來 Blueprint 紀錄**：
1. **Gateway Batch Payload (多實體設備打包)**：需在進入平台前，依賴 EMQX Rule Engine / Node-RED 進行解包，否則無法綁定 ISA-95 單一設備節點。
2. **High-Frequency Array (高頻波形陣列)**：針對振動頻譜 (FFT) 等龐大陣列，未來應引入針對性壓縮策略 (`bytea` 或 URI 參照)，不宜硬塞入現有 JSONB Schema。
3. **Sparkplug B / OPC UA PubSub**：因其強綁定狀態管理 (NBIRTH/DDEATH)，將作為 Phase 2 核心 Epic，並開發 Auto-discovery Plugin。
4. **Legacy Custom Protocol (純文字/CSV)**：應由 Edge 端前處理，或留待未來於平台內實作 Regex Extractor 與 Script Sandbox。

## 📝 API Contract Log

<!-- Backend 完成的 API endpoint 記在這裡，給 Frontend / MCP 對話參考 -->

### Namespace (prefix: `/api/v1/namespace`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| GET | `/tree` | 完整巢狀樹 | ✅ |
| POST | `/nodes` | 建立 node | ✅ |
| PUT | `/nodes/{id}/move` | 移動 (觸發 Live Migration) | ✅ |
| PUT | `/nodes/{id}/rename` | 重新命名 (含子 path 級聯) | ✅ |
| DELETE | `/nodes/{id}` | Soft delete | ✅ |
| PUT | `/nodes/{id}/persistence` | 設定 persist_mode | ✅ |
| GET | `/nodes/deleted` | 取得所有 Soft-deleted 的 Nodes (Recycle Bin) | ✅ |
| PUT | `/nodes/{id}/restore` | 資源回收桶：還原 Node | ✅ |
| DELETE | `/nodes/{id}/hard` | 資源回收桶：徹底刪除 Node | ✅ |

### Tags (prefix: `/api/v1/tags`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| POST | `/` | 建立 Tag（自動建立 mapping + audit） | ✅ |
| PUT | `/{tag_id}` | 更新 Tag 資訊 (支援類別變更與 Topic 同步) | ✅ |
| GET | `/{tag_id}/detail` | Tag 完整資訊（含 mappings + audit history） | ✅ |
| GET | `/{node_path}/list` | 列出 path 下所有 Tag | ✅ |
| GET | `/{tag_id}/values?from=&to=` | 歷史時序資料（by tag_id，跨 migration） | ✅ |
| GET | `/{tag_id}/latest` | 最新值 | ✅ |
| GET | `/by-topic/{topic}/values?from=&to=` | 用 MQTT topic 查（限 mapping 期間） | ✅ |
| GET | `/deleted` | 取得所有 Soft-deleted 的 Tags (Recycle Bin) | ✅ |
| DELETE | `/{tag_id}` | Soft delete Tag | ✅ |
| PUT | `/{tag_id}/restore` | 資源回收桶：還原 Tag | ✅ |
| DELETE | `/{tag_id}/hard` | 資源回收桶：徹底刪除 Tag（含 mapping、changelog、telemetry） | ✅ |

### Data (prefix: `/api/v1/data`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| POST | `/{topic_path}` | 寫入資料 (→ ts_raw_payloads) | ✅ |

### Schema Types (prefix: `/api/v1/schema-types`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| GET | `/` | 列出所有（過濾已刪除） | ✅ |
| GET | `/{type_id}` | 取得單一 | ✅ |
| POST | `/` | 建立（支援 `category`：telemetry/status/alarm/event/measurement/metrics） | ✅ |
| PUT | `/{type_id}` | 更新（支援 `category` 更新） | ✅ |
| DELETE | `/{type_id}` | Soft delete | ✅ |
| GET | `/deleted` | 取得所有 Soft-deleted 的 Schema Types (Recycle Bin) | ✅ |
| PUT | `/{type_id}/restore` | 資源回收桶：還原 Schema Type | ✅ |
| DELETE | `/{type_id}/hard` | 資源回收桶：徹底刪除 Schema Type | ✅ |

### System Settings (prefix: `/api/v1/system`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| GET | `/health` | Health check | ✅ |
| GET | `/info` | 平台版本、DB/EMQX 連線狀態、uptime | ✅ |
| GET | `/mqtt-stats` | EMQX 統計快照（proxy 轉發 EMQX REST API） | ✅ |
| WebSocket | `/mqtt-stats/ws` | 每 5 秒推送 EMQX 統計更新 | ✅ |
| GET | `/retention` | 各 hypertable 的 retention / compression 狀態 | ✅ |
| PUT | `/retention` | 修改 retention（Phase 2，目前回 501） | ✅ (stub) |

### AI Assistant (prefix: `/api/v1/ai`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| POST | `/chat` | Gemini + MCP Tools 對話（無 API Key 時 Mock 模式） | ✅ |

**Swagger UI**: http://localhost:8000/docs

### MCP Server (stdio transport)

| Type | Name | 說明 |
|---|---|---|
| Tool | `browse_namespace(path)` | 瀏覽 Namespace 子節點 |
| Tool | `query_telemetry(tag_id, start, end)` | 查詢歷史時序資料 |
| Tool | `get_latest_values(tag_ids[])` | 批次查詢最新值 |
| Resource | `uns://namespace/tree` | Namespace 全貌 |

## 📌 Legend

- ⬜ TODO
- 🔨 IN PROGRESS
- ✅ DONE
- ⚠️ BLOCKER (需先解決)

---

## 🛠️ 開發環境規範 (Strict)

- **環境隔離**：所有 Python 相關服務 (Backend, Data-Engine) **一律使用 `.venv`** 執行。
- **Backend 啟動**：`source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
- **Data-Engine 啟動**：確保在 `.venv` 環境下執行 `python main.py` 或相關 entry points。
