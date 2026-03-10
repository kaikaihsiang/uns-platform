# UNS Platform — Phase 2 (MVP) 功能開發與任務交辦計畫 (Domain Expert Directive)

**文件版本**: v1.1
**建立時間**: 2026-03-06
**文件性質**: 領域專家指導原則與跨角色 Agent 任務交辦清單

## 1. 總體經營與架構目標對齊 (Alignment with Phase 1 PoC)

本文件建立在 👉 `docs/poc_feature_scope.md` (Phase 1 PoC) 已打下的基礎上。
在 PoC 階段，我們驗證了資料流管線 (Data Engine)、動態架構 (Namespace Tree) 與基礎 AI 串接。

根據 `docs/platform_system_spec.md` 定義，**Phase 2 (MVP)** 的核心邊界必須包含：
1. **生產脈絡 (Production Context) 支援**：將單純的 IoT 數據升級為具有工廠營運意義的資料。沒有 Lot、Recipe、Equipment State 的綁定，數據就無法被有效查詢與分析。
2. **多表分流持久化 (Data Category Routing)**：將不同類型的資料 (Telemetry, Alarms, Events, Status 等) 儲存至專屬的 TimescaleDB 時序表中，這部分 ADR-003 已定義但在後端 ORM 中尚未完全落實。
3. **AI Copilot 進階化**：透過建立完整的生產脈絡，讓前台的 AI Agent 能夠回答如「這個 Lot 的 OEE 為何降低」等高階工業問題。
4. **DevOps 與持續整合 (CI/CD)**：作為合規要求極高的工業級產品 (針對製藥/CDMO)，必須建立自動化測試、代碼檢查與打包流程。

為了達到以上標，請各專業領域 Agent 依照下列**功能需求 (Feature/Requirement)** 認領並執行任務。

---

## 2. 任務交辦清單 (Task Delegation by Feature)

### 🎯 Feature 1: 生產脈絡 (Production Context) 核心建置

**業務價值**: 賦予設備資料靈魂。當設備發生告警時，系統必須知道當下是在生產哪個 Lot、執行哪支 Recipe，才能做到異常根本原因分析 (RCA)。
**架構定位 (Why it matters)**:
- `ProductionRun` 是 L1/L2 (連續感測數據) 與 L3 (業務邏輯如 MES/SPC) 之間的唯一橋樑。
- 透過在 UNS 就地綁定脈絡，巨量時序運算的負載 (Compute Workload) 得以留在 UNS，L3/L4 系統只需集中調用「結果」。
- 保持極度聚焦：與 L4 (ERP) 的交集僅限於「工單 (Work Order)」，不干涉排程與帳務，維持 UNS 作為「生產現場 Single Source of Truth」的純粹性。

#### 🧑‍💻 Backend Agent (`backend-engineer` / `fastapi-backend`)
- **任務 1.1**: 建立 `ProductionRun` 資料表 ✅ **DONE**
- **任務 1.2**: 開發 Production Context API ✅ **DONE**

#### 🧑‍💻 Data-Engine Agent (`data-engine-engineer`)
- **任務 1.3**: 強化 Event Consumer 綁定邏輯 ✅ **DONE**
- **任務 1.4**: Context 附加機制 (若需於 Pipeline 階段處理) ✅ **DONE**

#### 🧑‍💻 Frontend Agent (`frontend-agent` / `vercel-react-best-practices`)
- **任務 1.5**: 新增「當前批次 (Active Run)」看板 ✅ **DONE** (2026-03-06)
  - **規格**: 在設備狀態頁面增加資訊卡，即時顯示 `Active Lot`, `Recipe`, `Start Time`。
  - **API**: 已整合 `GET /api/v1/production-runs/active?equipment_path=xxx`
- **任務 1.6**: 批次歷史記錄檢視流程 ✅ **DONE** (2026-03-06)
  - **規格**: 建立 `Production Run History` 頁面，支援以設備或 Lot ID 篩選歷史記錄。
  - **API**: 發現後端缺漏並主動修復實作了 `GET /api/v1/production-runs/search` 補齊功能 (Hotfix 404)。

---

### 🎯 Feature 2: 完善時序資料庫 ORM 與架構同步

**業務價值**: 確保後端 API 與 MCP Server (LLM 查詢介面) 能夠正確讀取 Data Engine 寫入的分流資料表，避免架構脫節。
**技術現狀 (The ORM Gap)**:
- 雖然 Data Engine 已經依據 ADR-003 將資料聰明分流至 `ts_telemetry`, `ts_alarms`, `ts_events` 等多張實體表。但 Backend 程式 (SQLAlchemy) 目前只認識 `ts_telemetry`。
- 若不補齊，未來 MCP Server 將無法透過 ORM 語法查詢歷史警報或事件，導致「AI 自動診斷」功能因缺乏資料支撐而失效。

#### 🧑‍💻 DB/Schema Engineer (`db-schema-engineer`) & Backend Agent
- **任務 2.1**: 補齊 SQLAlchemy Models
  - **規格**: 依據已經定案的 ADR-003 與 Init SQL，在 `backend/app/models/__init__.py` 中加入漏掉的時序表模型定義：`TsEvents`, `TsAlarms`, `TsStatus`, `TsMeasurements`。
  - **要求**: 確定欄位定義 (例如 `details` JSONB 欄位) 與資料庫實體表完全相符。

---

### 🎯 Feature 3: AI Copilot 進階化 (讓 MVP 發光)

**業務價值**: 讓 AI 從單純的對話機器人，升級為能主動幫工程師找問題的智能助手。
**配置與驗證需求 (AI Integration)**:
- **API 金鑰配置**: 後端 (`api/v1/ai.py`) 已保留切換邏輯。需於根目錄 `.env` 設定 `gemini_api_key`，系統即依此自動從 Mock 切換為真實 Gemini API。
- **真實驗證**: 必須配合真實的生產資料與 MCP Tools 進行驗證，確保 LLM 能正確讀取 UNS 的 Namespace 與脈絡。

#### 🧑‍💻 Frontend Agent (`frontend-agent`)
- **任務 3.1**: 擴充 AI Chat Panel 提供 Quick Prompts 
  - **規格**: 在現有的 `/ai-assistant` 介面中新增情境化按鈕。
  - **Hotfix (2026-03-06)**: 發現 `gemini-2.0-flash` 模型已遭官方下架 (500 Error)，主動修復為 `gemini-2.5-flash`，AI 助手已順利復活。
- **任務 3.2**: Tag Management - Target Column Mapping UI ✅ **DONE** (2026-03-06)
  - **規格**: 更新 Tag 編輯與 Schema 設定頁面，落實 `target_column` 的下拉選擇與 `category` 的連動過濾。
  - **業務對齊**: 確保非 Telemetry 資料（如 Alarm, Status）能精準映射至 `state`, `severity`, `result` 等特定欄位，替代原本容易出錯的手動輸入機制。

---

### 🎯 Feature 4: DevOps 與 CI/CD 流程自動化

**業務價值**: 確保每次程式碼提交都不會破壞既有功能，為未來的團隊擴編與持續交付準備。

#### 🧑‍💻 Backend Agent & Data-Engine Agent
- **任務 4.1**: 建立 Backend 與 Data Engine CI Pipeline
  - **規格**: 建立 GitHub Actions 或 GitLab CI 的 YAML 檔。
  - **流程**: 包含自動執行 `pytest`、`flake8`/`black` 代碼格式檢查。

#### 🧑‍💻 Frontend Agent
- **任務 4.2**: 建立 Frontend CI Pipeline
  - **規格**: 將 Vite build 流程、`ESLint` 靜態掃描與 `TypeScript` 型別檢查自動化。

---

### 🚦 Future Epic: Runtime Visualization & AI Deep Dive (Phase 3.5)

**業務價值**: 將「工單流水帳」轉化為「可操作的工程洞察」，這是將 UNS 推向市場、讓決策者買單的關鍵一擊。

#### 🧑‍💻 Frontend Agent
- **任務 3.5.1**: 脈絡化下鑽分析 (Contextual Drill-down)
  - **規格**: 在 Run History 點擊特定批次時，展開 Drawer，自動調用該時段的 `ts_telemetry` 與 `ts_alarms`，繪製溫度/壓力波形圖與警報散佈圖。
- **任務 3.5.2**: OEE 與稼動狀態圖表
  - **規格**: 結合 `ts_status`，顯示特定生產批次期間的設備稼動狀態 (RUN/IDLE/DOWN) 甘特圖。

#### 🧑‍💻 Backend Agent & Frontend Agent
- **任務 3.5.3**: AI 根本原因分析 (Context-Aware AI RCA)
  - **規格**: 在 Run History Detail 頁面新增「一鍵 AI 診斷」按鈕。由 Frontend 帶入 `run_id` 呼叫 AI 介面，MCP 自動調取該批次的 Alarm 與 Telemetry 交由 LLM 總結異常根因。

---

## 3. 執行協議與回報機制 (Protocol)

1. **認領與開始**: 請各 Agent 在接獲使用者指令啟動對應任務時，**優先查看此文件**以確保對焦。
2. **完工回報**: 完成對應的任務 (Task 1.x ~ 4.x) 後，請務必更新專案根目錄下的 `PROGRESS.md` 文件，將對應的 Feature 標記為 IN PROGRESS 或 DONE，並附上簡短的 Pull Request 或 Commits 說明。
3. **跨邊界問題**: 遇到跨 API (例如 Frontend 需要 Backend 配合調整欄位) 時，請透過更新交辦文件或使用 Artifact 清楚明文約定 Payload 格式。

*此文件由 Industrial Domain Expert 建立，做為全團隊推進 MVP 的最高指導原則。*
