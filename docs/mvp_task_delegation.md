# UNS Platform — Phase 2 (MVP) 功能開發與任務交辦計畫 (Domain Expert Directive)

**文件版本**: v1.2
**最後更新**: 2026-03-12
**文件性質**: 領域專家指導原則與跨角色 Agent 任務交辦清單

## 1. 總體經營與架構目標對齊 (Alignment with Phase 1 PoC)

在 Phase 2 的後半段，我們的重心從「資料怎麼進來」轉向「資料怎麼出去且被正確理解」。
為了支撐 **工業級 RCA** 與 **AI 賦能**，我們必須建立一套**語義感知 (Semantic-Aware)** 的資料存取介面。

核心目標調整：
1. **Interface First**：不再只是提供 API，而是提供「具有工業語義的數據契約」。
2. **AI-Ready Data**：數據必須自帶單位、代碼翻譯與生產脈絡，讓 AI 不需預訓練也能理解工廠現況。
3. **高效能存取**：利用 gRPC 作為系統間通訊的骨幹，支撐高頻資料的批次查詢。

---

## 2. 任務交辦清單 (Task Delegation by Feature)

### 🎯 Feature 1: 生產脈絡 (Production Context) ✅ **DONE**
- **任務 1.1**: 建立 `ProductionRun` 資料表 ✅
- **任務 1.2**: 開發 Production Context API ✅
- **任務 1.3**: 強化 Event Consumer 綁定邏輯 ✅
- **任務 1.4**: Context 附加機制 (Pipeline 階段) ✅

### 🎯 Feature 2: 完善時序資料庫 ORM ✅ **DONE**
- **任務 2.1**: 補齊 SQLAlchemy Models (`TsEvents`, `TsAlarms` 等) ✅
- **任務 2.2**: 實作 `last_data_at` 高效批次更新機制 ✅ (2026-03-12)

### 🎯 Feature 3: 運作視覺化 (Runtime Visualization) 🔨 **IN PROGRESS**
- **任務 3.5.1**: 全維度同步 RCA 視圖 ✅ **DONE** (2026-03-12)
  * 實作單一整合圖表，精確對齊遙測、狀態、警報與事件。
- **任務 3.5.2**: OEE 與稼動狀態圖表 (整合於同步視圖) ✅ **DONE**
- **任務 3.5.3**: 一鍵 AI 根本原因分析 (AI RCA) ⬜ **TODO**
  * 待 Feature 5 基礎建設完成後啟動。

### 🎯 Feature 4: DevOps 與強健性 ✅ **DONE**
- **任務 4.1**: 建立 CI Pipeline (Ruff + Pytest) ✅
- **任務 4.2**: 實作「單一溢位出口」Robustness Bag ✅ (2026-03-11)

### 🚀 Feature 5: UNS 資料介面硬核化 (Semantic Data Access Layer) 🌟 **NEW**

**業務價值**: 這是平台的「出口」。穩固的介面能確保 AI 診斷的準確性，並降低系統整合成本。

#### 🧑‍💻 Backend Agent (`backend-engineer`)
- **任務 5.1: gRPC 核心服務建置 (`UNSDataService`)**
  - **規格**: 定義 `.proto` 文件，包含 `QueryTimeSeries`, `GetLatestSnapshot`, `GetProductionContext`。
  - **要求**: 支援一次查詢多個 `tag_id`，並自動合併跨表資料（Telemetry + Status）。
- **任務 5.2: REST API 語義化改造**
  - **規格**: 強化 `GET /values` 端點，回傳值必須包含來自 `TagMetadataCache` 的 `unit`, `label`, `data_type`。
  - **翻譯功能**: 自動將資料庫的 `state_code` 透過 `MasterDataCache` 轉換為可讀的 `label`（如 "PRD" -> "生產中"）。

#### 🧑‍💻 AI/MCP Specialist
- **任務 5.3: 擴展進階 MCP Tools**
  - **工具 A: `semantic_path_discovery`**：讓 AI 能透過語義路徑 (Enterprise/Site/...) 搜尋對應的 Tag ID。
  - **工具 B: `batch_context_analysis`**：提供特定批次 (run_id) 的數據統計摘要（Max/Min/Avg/AlarmCount）。
- **任務 5.4: 異常診斷 Prompt 範本開發**
  - **規格**: 建立 System Prompt，指導 LLM 如何組合 gRPC/REST 的資料進行 RCA。

---

## 3. 執行協議與回報機制 (Protocol)

1. **介面契約優先 (Schema-First)**：在實作 gRPC 之前，必須先產出 Protobuf 定義並與團隊 Align。
2. **AI 友好原則**：所有 API 輸出的 JSON 結構必須平坦且語義清晰，避免層次過深的巢狀結構。
3. **文件同步**：介面變更後，同步更新 `docs/platform_system_spec.md` 的第八章「資料存取介面」。

*此文件由 Industrial Domain Expert 與 Gemini CLI 共同維護，做為團隊推進的最高指導原則。*
