# UNS Namespace Data Platform

> **工廠資料的 Single Source of Truth + AI-Ready Factory Data Hub**

收 → 存 → 查 → 管，一個平台搞定。Namespace 改了，資料不斷。

## 專案結構

```
uns-platform/
├── docs/                    設計文件與規格
│   ├── product_vision.md       產品定位與 Roadmap
│   ├── platform_system_spec.md 系統規格書（16 章）
│   ├── uns_architecture_decisions.md  架構決策紀錄
│   ├── payload_standard_spec.md       Payload 標準
│   ├── topic_naming_guide.md          Topic 命名規範
│   ├── namespace_template.yaml        Namespace 範本
│   ├── uns_config_example.yaml        設定範本
│   └── payload_samples.json           Payload 範例
│
├── schemas/                 DB Schema（TimescaleDB）
│   ├── timeseries_schema.sql          核心時序表
│   ├── production_context_schema.sql  生產脈絡表
│   └── measurement_and_state_schema.sql SPC / 設備狀態表
│
├── backend/                 [TODO] FastAPI Backend
├── data-engine/             MQTT Consumer + Data Pipeline
│   ├── consumer_example.py
│   ├── production_context_consumer.py
│   ├── measurement_consumer.py
│   ├── equipment_state_consumer.py
│   └── cdc_mes_bridge/
│
├── frontend/                [TODO] React Namespace Manager UI
├── mcp-server/              [TODO] MCP Server for LLM Integration
│
├── ops/                     CLI 工具與運維
│   ├── spc_tool.py             SPC 分析工具
│   ├── oee_tool.py             OEE 計算工具
│   └── ...
│
├── docker-compose.yml       [TODO] 一鍵部署
└── .env.example             [TODO] 環境變數範本
```

## 技術選型

| 元件 | 技術 |
|---|---|
| MQTT Broker | EMQX Open Source 5.x |
| Database | TimescaleDB 2.x |
| Backend | FastAPI (Python) |
| Frontend | React + Vite + Ant Design 5 + dnd-kit |
| MCP Server | Python (MCP SDK) |
| 部署 | Docker Compose |

## 核心差異化

1. **Tag 身份分離 + Live Migration** — Namespace 搬了，歷史資料不斷
2. **Per-Topic Persistence Config** — 每個 topic 獨立設定存/不存/retention
3. **Production Context Layer** — IoT 資料自動關聯 Lot / Step / Recipe
4. **MCP Server** — 讓任何 LLM Agent 都能和工廠資料互動

## 目標市場

🥇 製藥 CDMO + 精密化學 | 🥈 食品飲料 + 電子代工

## 文件導覽

- [產品願景](docs/product_vision.md)
- [系統規格書](docs/platform_system_spec.md)
- [架構決策紀錄](docs/uns_architecture_decisions.md)
