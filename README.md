# UNS Namespace Data Platform

> **工廠資料的 Single Source of Truth + AI-Ready Factory Data Hub**

收 → 存 → 查 → 管，一個平台搞定。Namespace 改了，資料不斷。

> **狀態**：PoC + Phase 2 大部分完成，開發中斷約 4 個月（最後 commit 2026-03-17）
> 於 2026-07-21 重新盤點。目前唯一未完成的主線是 **Feature 5 語義資料層
> (ADR-005)**：`QueryHistory` 仍是 placeholder，`SearchNamespace` REST 未接
> attributes，semantic E2E 未納入 CI。細節見 [PROGRESS.md](PROGRESS.md) 與
> [_memory/_context.md](_memory/_context.md)（開工前必讀，兩者互補：PROGRESS.md
> 是 feature 級進度看板，`_memory/_context.md` 是給任何 AI 工具的現況儀表板）。

## 專案結構

```
uns-platform/
├── docs/                    設計文件與規格
│   ├── product_vision.md       產品定位與 Roadmap
│   ├── platform_system_spec.md 系統規格書（16 章）
│   ├── adr/                    架構決策紀錄 (ADR-001~005)
│   ├── handover/                跨 agent 交接文件
│   ├── payload_standard_spec.md       Payload 標準
│   ├── topic_naming_guide.md          Topic 命名規範
│   ├── namespace_template.yaml        Namespace 範本
│   └── payload_samples.json           Payload 範例
│
├── schemas/                 DB Schema（TimescaleDB，SQL 定義來源）
│
├── backend/                 FastAPI Backend（REST + gRPC，MCP 呼叫入口）
├── data-engine/             MQTT Consumer + Data Pipeline（唯一寫入時序 DB 的元件）
│   └── cdc_mes_bridge/         MES CDC Bridge
│
├── frontend/                 React + Vite + Ant Design Namespace Manager UI
├── mcp-server/                MCP Server（stdio transport，供 LLM Agent 存取）
│
├── ops/                      服務啟停、DB 重置、Namespace seed 等標準腳本
├── demo/                     模擬器與端到端驗證腳本（run_test.sh 等）
│
├── docker-compose.yml        EMQX + TimescaleDB 一鍵部署
├── .env.example               環境變數範本
│
└── _memory/                  廠商中立 SSOT 記憶層（給 AI 工具的現況入口）
```

## 技術選型

| 元件 | 技術 |
|---|---|
| MQTT Broker | EMQX Open Source 5.x |
| Database | TimescaleDB 2.x |
| Backend | FastAPI (Python, async) + gRPC |
| Frontend | React + Vite + Ant Design 5 + dnd-kit |
| MCP Server | Python (MCP SDK) |
| 部署 | Docker Compose |
| CI | GitHub Actions（Backend / Data-Engine / Frontend 全綠） |

## 快速開始

```bash
ops/start_all.sh        # 啟動 EMQX + TimescaleDB + Backend + Data Engine + Frontend
ops/seed_namespace.sh   # 匯入 ISA-95 Namespace 範例結構
demo/start_sim.sh       # 啟動智慧工廠模擬器，開始灌測試資料
demo/run_test.sh        # 執行端到端驗證測試
ops/stop_all.sh         # 關閉所有服務
```

> 所有 Python 服務一律在 `.venv` 下執行，**禁止直接用系統 Python** 或手動
> `python`/`uvicorn` 繞過上述標準腳本，詳見 [AGENTS.md](AGENTS.md)。

- Backend Swagger UI: http://localhost:8000/docs
- EMQX Dashboard: http://localhost:18083

## 核心差異化

1. **Tag 身份分離 + Live Migration** — Namespace 搬了，歷史資料不斷
2. **Per-Topic Persistence Config** — 每個 topic 獨立設定存/不存/retention
3. **Production Context Layer** — IoT 資料自動關聯 Lot / Step / Recipe
4. **語義資料存取層 (ADR-005，部分完成)** — gRPC/REST 語義路徑查詢與寫回，讓外部系統/AI 不需知道內部 `tag_id`
5. **MCP Server** — 讓任何 LLM Agent 都能和工廠資料互動

## 目標市場

🥇 製藥 CDMO + 精密化學 | 🥈 食品飲料 + 電子代工

## 文件導覽

- [產品願景 & Roadmap](docs/product_vision.md)
- [系統規格書](docs/platform_system_spec.md)
- [架構決策紀錄 (ADR)](docs/adr/)
- [進度看板 (Feature 級)](PROGRESS.md)
- [團隊分工與協作規則](AGENTS.md)
- [記憶層現況儀表板](_memory/_context.md)
