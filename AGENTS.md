# UNS Platform — Agent Team Members

## 團隊架構

```
                    ┌─────────────────────┐
                    │   YOU (Architect)   │
                    │   架構決策 + 指揮     │
                    └─────────┬───────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
   ┌─────▼─────┐    ┌────────▼────────┐   ┌──────▼──────┐
   │ Agent A    │    │   Agent B       │   │  Agent C    │
   │ Backend    │    │   Data Engine   │   │  Frontend   │
   │ Engineer   │    │   Engineer      │   │  Engineer   │
   └─────┬─────┘    └────────┬────────┘   └─────────────┘
         │                   │
   ┌─────▼─────┐    ┌────────▼────────┐
   │ Agent D    │    │   Agent E       │
   │ DB/Schema  │    │   Industrial    │
   │ Engineer   │    │   Domain Expert │
   └───────────┘    └─────────────────┘
```

## Agent 角色定義

### Agent A — Backend Engineer

| 項目 | 說明 |
|---|---|
| **負責** | FastAPI REST/gRPC API、ACL 管理、Migration Engine、MCP Server |
| **技術** | Python, FastAPI, gRPC, SQLAlchemy, Pydantic |
| **Skills** | `fastapi-backend`, `mqtt-emqx-integration` |
| **產出** | `backend/`, `mcp-server/` |

### Agent B — Data Engine Engineer

| 項目 | 說明 |
|---|---|
| **負責** | MQTT Consumer、Payload Decoder、Schema Matcher、Field Extractor、DB Writer |
| **技術** | Python, gmqtt/paho-mqtt, JSONPath, psycopg2 |
| **Skills** | `mqtt-emqx-integration`, `uns-namespace-design`, `timescaledb-schema` |
| **產出** | `data-engine/` |

### Agent C — Frontend Engineer

| 項目 | 說明 |
|---|---|
| **負責** | Namespace Manager UI（Tree Editor、Tag CRUD、Schema Type 管理、ACL 設定）|
| **技術** | React 18, TypeScript, Vite, Ant Design 5, dnd-kit |
| **Skills** | `vercel-react-best-practices`, `uns-namespace-design` |
| **產出** | `frontend/` |

### Agent D — DB/Schema Engineer

| 項目 | 說明 |
|---|---|
| **負責** | TimescaleDB schema 設計、migration、retention policy、compression |
| **技術** | SQL, TimescaleDB, Alembic, PostgreSQL |
| **Skills** | `timescaledb-schema` |
| **產出** | `schemas/` |

### Agent E — Industrial Domain Expert

| 項目 | 說明 |
|---|---|
| **負責** | Payload 標準、ISA-95 階層、Event 大類、SPC/OEE 邏輯、Production Context |
| **技術** | Domain knowledge, YAML, Python |
| **Skills** | `industrial-domain`, `uns-namespace-design` |
| **產出** | `docs/`, `ops/` |

## 協作規則

1. **所有 Agent 共用** `docs/platform_system_spec.md` 作為系統規格的 single source of truth
2. **API 契約** 由 Agent A 定義（OpenAPI + Protobuf），Agent B/C/D 遵循
3. **DB Schema** 由 Agent D 定義，Agent A/B 使用
4. **Namespace 規範** 由 Agent E 定義，所有 Agent 遵循
   - **Backend Service**：啟動時一律使用 `.venv` 虛擬環境，指令固定使用：`uvicorn app.main:app --reload --port 8000` (或加上 `--host 0.0.0.0`)
   - **Data-Engine Service**：所有服務啟動前，一律先啟動並使用 `.venv` 虛擬環境
   - **標準工具與操作**：驗證或控制系統（啟動、關閉、重置、模擬器）時，必須優先使用 `ops/` 與 `demo/` 目錄下準備好的 shell scripts（如 `start_all.sh`, `run_demo.sh` 等）。
    - **核心原則**：嚴禁直接使用系統 Python install 套件。所有 Agent 必須嚴格遵從下方的「標準腳本與工具清單」，禁止自行繞過腳本進行手動操作。

## 標準腳本與工具清單 (Standard Operational Scripts)

為了確保環境隔離性與操作一致性，所有 Agent 在執行啟動、關閉、資料初始化或模擬測試時，**必須且僅能**使用以下腳本：

### 1. 服務啟停管理 (Service Control)
- **全系統啟動/關閉**：`ops/start_all.sh`, `ops/stop_all.sh`
- **基礎設施 (MQTT/DB)**：`ops/start_infra.sh`
- **個別服務啟動**：
  - Backend REST/gRPC: `ops/start_backend.sh`
  - Data Engine (Consumer): `ops/start_data_engine.sh`
  - Frontend UI: `ops/start_frontend.sh`

### 2. 資料庫與命名空間管理 (DB & Namespace)
- **資料庫重置** (清除所有資料並重新建立 schema): `ops/reset_db.sh`
- **命名空間初始化** (匯入 ISA-95 Tree 結構): `ops/seed_namespace.sh`

### 3. 測試、模擬與 Demo (Testing & Simulation)
- **啟動模擬器** (啟動虛擬工廠資料流): `demo/start_sim.sh`
- **停止模擬器**: `demo/stop_sim.sh`
- **執行完整 Demo 流程**: `demo/run_demo.sh`
- **執行系統驗證測試**: `demo/run_test.sh`

## 跨對話協作機制（PROGRESS.md）

所有 Agent 在不同對話視窗中平行工作時，透過 `PROGRESS.md` 同步進度。

### 必須遵守的 5 條規則

1. 📖 **開工前讀** — 開始任何工作前，先讀 `PROGRESS.md`，了解其他 Agent 的進度和 blocker。
2. ✏️ **做完後寫** — 完成一個段落（Feature / 子任務）後，更新 `PROGRESS.md` 的狀態和備註。
3. 🚨 **有問題寫 blocker** — 遇到需跨元件討論或等待其他 Agent 時，寫到 `PROGRESS.md` 的「Blockers」段落。
4. 🐍 **一律使用 .venv** — 所有服務開發與執行，必須在 `.venv` 環境下進行。
5. 🛠️ **禁止手動操作服務** — 嚴禁 Agent 使用手動指令（如 `python ...` 或 `uvicorn ...`）繞過標準腳本。啟動、開關、重置或啟動模擬器，**必須使用上述 `ops/` 與 `demo/` 內的指定腳本**。

### 必讀的共用文件

開始工作前，除了 `PROGRESS.md`，還必須讀：
- `docs/poc_feature_scope.md` — PoC 的功能範圍與驗收標準
- `docs/platform_system_spec.md` — 系統規格（讀你負責的章節）
- `AGENTS.md` — 本文件（了解團隊分工）
