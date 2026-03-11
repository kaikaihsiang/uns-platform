# Feature 4: 工業級自動化測試與 DevOps 實作計畫 (Implementation Plan)

**文件版本**: v1.0  
**建立日期**: 2026-03-09  
**文件性質**: 測試策略、執行路徑與資源整合規範

## 1. 測試策略 (Testing Strategy)

我們不採取「純理論派」的測試寫法，而是採取 **「資產回收再利用」** 策略。我們將利用現有的模擬器、Seeding 腳本與資料庫重置邏輯，快速建立一套具備「工業真實感」的測試網。

### 核心原則：
1. **資料隔離**：測試應在 `uns_test` 資料庫或獨立 Schema 中執行，絕不干擾開發環境。
2. **模擬驅動**：利用 `smart_factory_sim.py` 的邏輯作為測試資料輸入源。
3. **契約優先**：優先驗證 API 與 Pipeline 的 Data Contract (JSONPath / Schema Mapping)。

---

## 2. 既有資產整合清單 (Asset Reuse)

| 既有資產 | 測試用途 | 整合方式 |
| :--- | :--- | :--- |
| `demo/smart_factory_sim.py` | **Traffic Generator** | 封裝為 Test Helper，模擬各類工業訊息進入 Pipeline。 |
| `ops/scripts/seed_namespace.py` | **Test Fixtures** | 轉化為 `pytest` fixture，為每個測試自動建立基礎樹狀結構。 |
| `docs/payload_samples.json` | **Golden Dataset** | 作為單元測試的 Input/Output 標準答案。 |
| `ops/reset_db.sh` | **Environment Reset** | 修改為支援 `TEST_DB` 變數，用於測試前後的環境清空。 |

---

## 3. 任務交辦清單 (Task List)

### 🚀 Phase 1: 基礎設施與環境隔離 (Infrastructure)
* [ ] **Task 4.1.1 [後端]**: 安裝 `pytest`, `pytest-asyncio`, `httpx` 並建立 `backend/tests/conftest.py`。
* [ ] **Task 4.1.2 [後端]**: 實作測試資料庫自動初始化邏輯（調用 `seed_namespace.py` 邏輯）。
* [ ] **Task 4.1.3 [資料引擎]**: 建立 `data-engine/tests/conftest.py`，配置 Mock MQTT Broker。
* [ ] **Task 4.1.4 [前端]**: 安裝 `vitest`, `happy-dom` 並配置 `@/` Alias 支援。

### 🧪 Phase 2: 核心邏輯單元測試 (Unit Testing)
* [ ] **Task 4.2.1 [後端]**: 測試 `NamespaceService` 的路徑計算與移動邏輯。
* [ ] **Task 4.2.2 [資料引擎]**: 測試 `FieldExtractor` 對於 `payload_samples.json` 中各種巢狀結構的解析。
* [ ] **Task 4.2.3 [資料引擎]**: 測試 `AutoDetector` 的遞迴 JSONPath 生成能力。

### 🔗 Phase 3: 整合與契約測試 (Integration Testing)
* [ ] **Task 4.3.1 [後端]**: 實作 `PUT /nodes/{id}/schema` 的 E2E 測試（資料庫聯動驗證）。
* [ ] **Task 4.3.2 [資料引擎]**: 實作完整 Pipeline 測試：從 `smart_factory_sim` 邏輯產生訊息 -> Pipeline 處理 -> 檢查 DB Writer 呼叫。
* [ ] **Task 4.3.3 [前端]**: 測試 `useNamespaceStore` 的狀態更新與錯誤處理。

### 🤖 Phase 4: CI 自動化管道 (Continuous Integration)
* [ ] **Task 4.4.1 [Linting]**: 設定 `ruff` 進行 Python 代碼風格與品質檢查。
* [ ] **Task 4.4.2 [Workflow]**: 建立 `.github/workflows/ci.yml`，在每次 PR 時自動執行上述所有測試。

---

## 4. 執行協議 (Execution Protocol)

1. **優先順序**：先完成 **Phase 1**，確保測試能動，再進入核心邏輯開發。
2. **回報機制**：完成任務後，請 Agent 同步更新此文件，並在 `PROGRESS.md` 標註。
3. **失敗處理**：若測試失敗，禁止強制合併代碼，必須優先修復測試。

---
*此文件由 Gemini CLI 顧問建立，作為 Feature 4 開發的最高準則。*
