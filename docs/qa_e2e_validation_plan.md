# UNS Platform — MVP E2E Validation & Demo Readiness (Product QA Plan)

**文件版本**: v1.0
**建立時間**: 2026-03-06
**文件性質**: QA 測試計畫與 Demo 模擬器開發指引

## 1. 核心驗證目標 (Validation Goals)

在推進更多前端功能或 AI 進階應用之前，我們必須確保底層的「數據引擎 (Data Engine)」與「時序資料庫 (TimescaleDB)」能夠完美接住並關聯真實工廠的高頻資料流。

**本階段 (Demo Readiness) 的三大 QA 驗收指標**：
1. **Dynamic Data Flow**: 系統必須能吃下連續不斷的 MQTT 負載，並正確觸發 Schema Decoder 與 Category Routing。
2. **Context Enrichment**: 所有的 Telemetry 與 Alarms 寫入資料庫時，都必須 100% 成功黏上當下活躍的 `Lot_ID` 與 `Run_ID`。
3. **AI Verifiability**: 在產生至少 5 個批次 (Lot) 的資料且帶有幾次 Alarm 後，Gemini 必須能透過 MCP API 精準回答出「剛剛在哪個 Lot 發生了溫度超標警報」。

---

## 2. 模擬器開發任務交辦 (Simulator Development Tasks)

為了達成上述 QA 驗證，我們需要打造一支專屬的**智慧工廠行為模擬器**。

### 🧑‍💻 Task QA-1: 開發 `demo/smart_factory_sim.py` 
**Owner**: Backend Agent 或 Data-Engine Agent
**Location**: `demo/smart_factory_sim.py`
**Dependencies**: `paho-mqtt` 或 `gmqtt` (依照既有套件庫)

**實作規格與劇本要求**：
1. **MQTT 推播能力**：腳本啟動後，必須持續連線至 `localhost:1883`。
2. **設備心跳 (Telemetry Simulation)**：
   - 目標設備：`TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Status` (或符合現有 Namespace 的路徑)
   - 頻率：每 1~2 秒發送一筆資料。
   - 參數：`temperature` (預設 25.0，加入微小隨機浮動)、`pressure` (預設 1.2)。
3. **生產脈絡切換 (Lot Event Simulation)**：
   - 腳本需要有一個事件迴圈，例如「每 20 筆 Telemetry 資料為一個 Lot 週期」。
   - 週期開始：發送 `LOT_START` MQTT 事件至指定的 Event Topic。
   - 週期結束：發送 `LOT_END` 事件。
   - 腳本需要自動生成累加的 Lot ID (如 `LOT-SIM-001`, `LOT-SIM-002`)。
4. **異常觸發機制 (Alarm Injection)**：
   - 每個 Lot 在生產期間，有 30% 機率會發生「溫度飆過 35.0 度」的異常。
   - 發生異常時，除了 Telemetry 數值飆高，還要**額外發送一筆 Alarm 報文** 至 Alarm Topic (Level: HIGH)。

---

## 3. E2E 走查檢核表 (Self-QA Checklist for Product Owner)

當 `smart_factory_sim.py` 成功開發並跑起來後，請 Product Owner (您自己) 依照以下步驟親自走查：

- [ ] **Step 1: 啟動環境與模擬器**
  - 啟動 docker-compose (EMQX, DB)。
  - 啟動 FastAPI Backend (`.venv/bin/uvicorn`)。
  - 啟動 Data Engine (`.venv/bin/python main.py`)。
  - 執行 `python demo/smart_factory_sim.py`，讓它在背景跑 3~5 分鐘。

- [ ] **Step 2: 驗證 Data Category Routing (PostgreSQL 檢查)**
  - 連進 DB (或透過 PgAdmin/DBeaver)，檢查 `ts_telemetry` 是否有數百筆資料。
  - 檢查 `ts_events` 是否有 `LOT_START`, `LOT_END`。
  - 檢查 `ts_alarms` 是否有被模擬器觸發的警報。

- [ ] **Step 3: 驗證 Production Context (Frontend 看板檢查)**
  - 打開 Frontend 設備節點頁面，確認「當前批次 (Active Run)」資訊卡有跟隨模擬器動態跳動更新 Lot ID。
  - 進入 `Run History` 頁面，確認有列出剛剛跑完的 3~5 個模擬 Lot，且起訖時間合理。

- [ ] **Step 4: AI RCA Demo 挑戰 (最終魔王關)**
  - 開啟 Frontend 內建的 `/ai-assistant`。
  - 輸入提問：「請幫我找出今天 (或最近 1 小時) 發生溫度超標 Alarm 的 Lot ID，並告訴我總共超標了幾次。」
  - 預期結果：Gemini 透過 MCP 呼叫 Backend API，精準撈出 `ts_alarms` 裡的紀錄，並附帶 `ts_alarms` 裡記載的 `Lot_ID` (因為 Data Engine 已經成功把 Context 黏上去了)。

如果以上四步都能順暢走完，我們的 MVP 就已經具備了強勢的「防彈展示 (Bulletproof Demo)」能力，我們就可以安心切入 Phase 3.5 的「圖表連動」開發了！
