# Backend Agent 任務交辦書: System Settings APIs + AI Chat API

> **來自**: Frontend Agent (Agent C)
> **交辦給**: Backend Agent (Agent A)
> **目的**: 實作 6 支新 API，讓 Frontend 可以完成「系統設定」與「AI 助手」兩個功能頁面。
> **開工前**: 請先閱讀 `PROGRESS.md` 中的 Handover 區塊。

---

## 📋 任務清單

| # | API | Method | 路徑 | 優先級 |
|---|---|---|---|---|
| 1 | 平台資訊 | GET | `/api/v1/system/info` | **P0** |
| 2 | MQTT 統計 | GET | `/api/v1/system/mqtt-stats` | P1 |
| 3 | MQTT 即時推播 | WebSocket | `/api/v1/system/mqtt-stats/ws` | P1 |
| 4 | 資料保留策略 | GET | `/api/v1/system/retention` | P2 |
| 5 | 修改保留策略 | PUT | `/api/v1/system/retention` | P2 (可先 stub) |
| 6 | AI 對話 | POST | `/api/v1/ai/chat` | **P0** |

---

## Task 1: `GET /api/v1/system/info`

### 用途
前端 System Settings 頁面的「平台資訊」卡片，顯示各服務連線狀態。

### Response Schema
```json
{
  "platform_version": "0.1.0",
  "backend_status": "ok",
  "database": {
    "status": "connected",
    "version": "PostgreSQL 16.x + TimescaleDB 2.x",
    "connection_pool": { "size": 10, "checked_out": 2 }
  },
  "mqtt_broker": {
    "status": "connected",
    "host": "localhost:1883",
    "version": "EMQX 5.x"
  },
  "uptime_seconds": 45234
}
```

### 實作提示
- `platform_version` 可 hardcode 在 `config.py`
- DB 狀態: 用 `SELECT version()` + engine pool status
- EMQX 狀態: `GET http://localhost:18083/api/v5/status`（EMQX REST API）
- `emqx_api_url` 已在 `config.py` 中定義為 `http://localhost:18083`
- Backend uptime: 記錄 `app.state.start_time` 於 lifespan startup

---

## Task 2: `GET /api/v1/system/mqtt-stats`

### 用途
前端「MQTT Broker 狀態」卡片的一次性快照。

### Response Schema
```json
{
  "connected_clients": 3,
  "topics_count": 14,
  "subscriptions_count": 7,
  "messages_received_total": 12345,
  "messages_sent_total": 6789,
  "messages_per_second": 2.5,
  "retained_messages_count": 8
}
```

### 實作提示
- Proxy 轉發 EMQX REST API: `GET http://localhost:18083/api/v5/stats`
- EMQX 預設帳密: `admin` / `public`（`httpx.BasicAuth`）
- 欄位對應參考 [EMQX Stats API Docs](https://docs.emqx.com/en/emqx/v5.8/admin/api-docs.html)

---

## Task 3: WebSocket `/api/v1/system/mqtt-stats/ws`

### 用途
前端透過 WebSocket 即時接收 MQTT Broker 統計更新（每 5 秒推播一次）。

### 行為規格
1. 前端建立 WebSocket 連線
2. Backend 每 5 秒輪詢 EMQX REST API，推送最新統計 JSON
3. 前端關閉連線時，Backend 停止輪詢

### 實作範例 (FastAPI)
```python
from fastapi import WebSocket, WebSocketDisconnect
import asyncio, httpx

@router.websocket("/system/mqtt-stats/ws")
async def mqtt_stats_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            stats = await fetch_emqx_stats()  # 複用 Task 2 的邏輯
            await websocket.send_json(stats)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
```

---

## Task 4: `GET /api/v1/system/retention`

### 用途
前端「資料保留策略」卡片，顯示各 hypertable 的 retention / compression 狀態。

### Response Schema
```json
{
  "policies": [
    {
      "table_name": "ts_telemetry",
      "retention_days": 365,
      "compression_enabled": true,
      "compress_after_days": 7
    },
    {
      "table_name": "ts_raw_payloads",
      "retention_days": 30,
      "compression_enabled": false,
      "compress_after_days": null
    }
  ]
}
```

### 實作提示
- 查詢 TimescaleDB 內建 view: `timescaledb_information.jobs` + `timescaledb_information.compression_settings`
- 或用: `SELECT * FROM timescaledb_information.data_retention_policies`

---

## Task 5: `PUT /api/v1/system/retention` (Phase 2, 可先 stub)

PoC 階段可先回 `501 Not Implemented`：
```python
@router.put("/system/retention")
async def update_retention():
    raise HTTPException(501, "Retention policy modification is planned for Phase 2")
```

---

## Task 6: `POST /api/v1/ai/chat` ⭐ 核心

### 用途
前端 AI Chat Panel 送出使用者訊息，Backend 呼叫 Gemini API + MCP Tools，回傳 AI 回覆。

### 架構決策（已確認）
- **LLM**: Gemini 優先（`google-genai` SDK），架構預留 OpenAI 切換
- **MCP Tools**: **In-process import**（直接 import `mcp-server/server.py` 中的函式，不走 subprocess）
- **環境變數**: 需在 `backend/.env` 新增 `gemini_api_key`

### Request Schema
```json
{
  "message": "列出 SMT 產線上所有的設備",
  "history": [
    { "role": "user", "content": "你好" },
    { "role": "assistant", "content": "你好！我是 UNS AI 助手..." }
  ]
}
```

### Response Schema
```json
{
  "reply": "在 TaiwanPrecision/Taoyuan/SMT/Line1 下有以下設備...",
  "tools_used": [
    {
      "name": "browse_namespace",
      "args": { "path": "TaiwanPrecision/Taoyuan/SMT/Line1" },
      "result": "{ ... }"
    }
  ]
}
```

### 實作指引

#### Step 1: 設定 config.py
```python
# config.py 新增
gemini_api_key: str = ""  # .env: gemini_api_key
llm_provider: str = "gemini"  # "gemini" | "openai" (Phase 2)
```

#### Step 2: 建立 AI Service (`backend/app/services/ai_service.py`)

```python
"""
核心邏輯：
1. 接收 user message + history
2. 定義 MCP tools 為 Gemini function declarations
3. 呼叫 Gemini API (with tool definitions)
4. 如果 Gemini 回傳 tool_call → 執行對應的 MCP 函式 → 回傳結果給 Gemini
5. 重複直到 Gemini 回傳純文字回覆
6. 回傳 reply + tools_used
"""
```

#### Step 3: MCP Tools 的 In-process 呼叫方式

MCP Server 檔案位於 `mcp-server/server.py`，裡面有 3 個 async 函式：
- `browse_namespace(path: str) → str`
- `query_telemetry(tag_id: int, start: str, end: str, limit: int) → str`
- `get_latest_values(tag_ids: list[int]) → str`

這些函式內部用 `httpx.AsyncClient` 呼叫 Backend REST API。
在 Backend 內使用時，可以直接 import 並呼叫（它們本質上就是 REST API 的 wrapper）。

**或者更簡單的做法**：直接在 `ai_service.py` 中建立 wrapper 函式，直接呼叫自己的 service layer（避免 HTTP 繞圈）。

#### Step 4: Gemini Tool Definition 範例

```python
from google import genai

tools = [
    genai.types.Tool(function_declarations=[
        genai.types.FunctionDeclaration(
            name="browse_namespace",
            description="瀏覽 Namespace 的子節點...",
            parameters=genai.types.Schema(
                type="OBJECT",
                properties={"path": genai.types.Schema(type="STRING", description="Namespace path")},
            ),
        ),
        # ... 其他 tools
    ])
]
```

#### Step 5: System Prompt 建議

```
你是 UNS Platform AI 助手。你可以使用以下工具查詢工廠資料：
- browse_namespace: 瀏覽 Namespace 結構
- query_telemetry: 查詢 Tag 歷史時序資料
- get_latest_values: 查詢 Tag 最新值

回答問題時，請依據工具回傳的實際資料回覆。若無相關資料，請如實告知。
使用繁體中文回覆。
```

---

## 新增路由與檔案

### 需要建立的檔案
| 檔案 | 說明 |
|---|---|
| `backend/app/api/v1/system.py` | System Settings 路由 (Tasks 1-5) |
| `backend/app/api/v1/ai.py` | AI Chat 路由 (Task 6) |
| `backend/app/services/ai_service.py` | AI + LLM + MCP 整合邏輯 |

### 需要修改的檔案
| 檔案 | 修改 |
|---|---|
| `backend/app/main.py` | 新增 `include_router(system.router)` + `include_router(ai.router)` + `app.state.start_time` |
| `backend/app/core/config.py` | 新增 `gemini_api_key`, `llm_provider` settings |
| `backend/.env` | 新增 `gemini_api_key=xxx` |
| `backend/requirements.txt` | 新增 `google-genai` |

---

## 驗證方式

完成後，請用以下指令驗證：

```bash
# Task 1
curl -s http://localhost:8000/api/v1/system/info | python3 -m json.tool

# Task 2
curl -s http://localhost:8000/api/v1/system/mqtt-stats | python3 -m json.tool

# Task 3 (WebSocket 測試)
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8000/api/v1/system/mqtt-stats/ws') as ws:
        msg = await ws.recv()
        print(json.loads(msg))
asyncio.run(test())
"

# Task 6
curl -s -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "列出所有根節點", "history": []}' | python3 -m json.tool
```

---

## 完成後

1. 更新 `PROGRESS.md` 中對應 Handover 區塊的狀態為 ✅
2. 回報 Frontend Agent: API 已就緒，可以開始前端串接
