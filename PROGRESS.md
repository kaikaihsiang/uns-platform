# UNS Platform — Development Progress Board

> **規則：每個 Agent 對話開始工作前必須讀取此檔案，完成一個段落後必須更新。**

---

## 🔵 Scaffolding

| 項目 | 狀態 | 完成時間 | 備註 |
|---|---|---|---|
| docker-compose.yml | ⬜ TODO | | EMQX + TimescaleDB + Backend + Frontend + Data Engine |
| .env.example | ⬜ TODO | | |
| DB Schema init | ⬜ TODO | | 跑 schemas/*.sql 到 TimescaleDB |
| Backend project init | ⬜ TODO | | FastAPI boilerplate |
| Frontend project init | ⬜ TODO | | Vite + React + AntD |
| Data Engine init | ⬜ TODO | | |

## 🟢 Feature Development

| Feature | 狀態 | Owner 對話 | 完成時間 | 備註 |
|---|---|---|---|---|
| F1: Namespace Tree 拖拉 | ⬜ TODO | | | |
| F2: MQTT → Consumer → DB | ⬜ TODO | | | |
| F3: Per-topic Persistence | ⬜ TODO | | | |
| F4: Tag + Live Migration | ⬜ TODO | | | |
| F5: REST API | ⬜ TODO | | | |
| F6: Schema Auto-detect | ⬜ TODO | | | |
| F7: MCP Server | ⬜ TODO | | | |
| F8: AI Demo | ⬜ TODO | | | |

## 🔴 Blockers / Decisions Needed

<!-- 任何 Agent 遇到需要跨對話討論的問題，記在這裡 -->

_（目前無）_

## 📝 API Contract Log

<!-- Backend 完成的 API endpoint 記在這裡，給 Frontend / MCP 對話參考 -->

_（尚未開始）_

## 📌 Legend

- ⬜ TODO
- 🔨 IN PROGRESS
- ✅ DONE
- 🚫 BLOCKED
