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
| Frontend project init | ⬜ TODO | | Vite + React + AntD |
| Data Engine init | ✅ DONE | 2026-03-03 | venv, gmqtt, db_writer 批次寫入機制 |

## 🟢 Feature Development

| Feature | 狀態 | Owner 對話 | 完成時間 | 備註 |
|---|---|---|---|---|
| F1: Namespace Tree 拖拉 | ⬜ TODO | | | |
| F2: MQTT → Consumer → DB | ✅ DONE | data-engine-agent | 2026-03-03 | Backend data API 已完成，Data Engine Pipeline (Decoder/SchemaMatcher/Deadband/DBWriter) 開發完成並通過整合測試 |
| F3: Per-topic Persistence | ⬜ TODO | | | persist_mode API 已完成 |
| F4: Tag + Live Migration | ✅ DONE | backend-engineer | 2026-03-03 | Tag CRUD + auto mapping + migration audit |
| F5: REST API | ✅ DONE | backend-engineer | 2026-03-03 | 13+ endpoints |
| F6: Schema Auto-detect | ⬜ TODO | | | |
| F7: MCP Server | ✅ DONE | backend-engineer | 2026-03-03 | 3 tools + 1 resource |
| F8: AI Demo | ⬜ TODO | | | |

## 🔴 Blockers / Decisions Needed

<!-- 任何 Agent 遇到需要跨對話討論的問題，記在這裡 -->

_（目前無）_

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

### Tags (prefix: `/api/v1/tags`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| POST | `/` | 建立 Tag（自動建立 mapping + audit） | ✅ |
| GET | `/{tag_id}/detail` | Tag 完整資訊（含 mappings + audit history） | ✅ |
| GET | `/{node_path}/list` | 列出 path 下所有 Tag | ✅ |
| GET | `/{tag_id}/values?from=&to=` | 歷史時序資料（by tag_id，跨 migration） | ✅ |
| GET | `/{tag_id}/latest` | 最新值 | ✅ |
| GET | `/by-topic/{topic}/values?from=&to=` | 用 MQTT topic 查（限 mapping 期間） | ✅ |

### Data (prefix: `/api/v1/data`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| POST | `/{topic_path}` | 寫入資料 (→ ts_raw_payloads) | ✅ |

### Schema Types (prefix: `/api/v1/schema-types`)

| Method | Path | 說明 | 狀態 |
|---|---|---|---|
| GET | `/` | 列出所有 | ✅ |
| GET | `/{type_id}` | 取得單一 | ✅ |
| POST | `/` | 建立 | ✅ |
| PUT | `/{type_id}` | 更新 | ✅ |
| DELETE | `/{type_id}` | 刪除 | ✅ |

### System

| Method | Path | 說明 |
|---|---|---|
| GET | `/health` | Health check |

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
- 🚫 BLOCKED
