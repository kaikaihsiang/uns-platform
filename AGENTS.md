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

## 跨對話協作機制（PROGRESS.md）

所有 Agent 在不同對話視窗中平行工作時，透過 `PROGRESS.md` 同步進度。

### 必須遵守的 3 條規則

1. 📖 **開工前讀** — 開始任何工作前，先讀 `PROGRESS.md`，了解其他 Agent 的進度和 blocker
2. ✏️ **做完後寫** — 完成一個段落（Feature / 子任務）後，更新 `PROGRESS.md` 的狀態和備註
3. 🚨 **有問題寫 blocker** — 遇到需要跨元件討論或等待其他 Agent 的情況，寫到 `PROGRESS.md` 的「Blockers」段落，Architect 會在主對話中決策

### 必讀的共用文件

開始工作前，除了 `PROGRESS.md`，還必須讀：
- `docs/poc_feature_scope.md` — PoC 的功能範圍與驗收標準
- `docs/platform_system_spec.md` — 系統規格（讀你負責的章節）
- `AGENTS.md` — 本文件（了解團隊分工）
