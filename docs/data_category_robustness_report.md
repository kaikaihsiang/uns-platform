# 📊 UNS 資料類別健壯性 (Robustness) 與自動溢位架構報告

**文件編號：** ARCH-2026-005 (Full Report)
**日期：** 2026-03-11
**參與者：** Kai-Hsiang (Yokogawa DX Consultant), Gemini CLI (Industrial & Backend Expert)
**狀態：** 決策核准 (Approved for Implementation)

---

## 1. 討論背景與初步動議 (Initial Inquiry)
使用者提出將系統現有的 6 個 `schema_category` 擴充至 9 個，新增類別包含：
*   **RecipeEvent**: 配方指令與參數變更。
*   **Maintenance**: 維修保養動作與設備狀態。
*   **QualitySamples**: 品質抽樣測量。

**討論核心問體：** 如何在維持架構抽象化（Generic）的同時，處理工業現場高度多樣化且動態變動的 Payload？

---

## 2. 專家評估與架構決策 (Architectural Decision)

### 2.1 語義映射 (Semantic Mapping)
經過對 ISA-95 標準與系統擴展性的評估，決定 **維持 6 個核心類別**。新增的業務需求應透過「語義映射」整合至現有框架：

| 業務類別 | 建議映射類別 (Table) | 區分屬性 (Discriminator) |
| :--- | :--- | :--- |
| **RecipeEvent** | `event` | `code_category = 'recipe'` |
| **Maintenance** | `event` (動作) / `status` (狀態) | `code_category = 'maintenance'` |
| **QualitySamples** | `measurement` | `code_category = 'quality'` |

### 2.2 核心原則：Core Columns + Overflow JSONB
*   **核心欄位 (Static Columns)**: 保留高頻查詢與基礎分析所需的欄位（如 `lot_id`, `state`, `value`, `result`）。這些欄位在資料庫中獨立存在，提供極致性能。
*   **自動溢位 (Overflow JSONB)**: 將所有非核心、動態變動、或設備特有的欄位自動打包進 `details` (in events/status) 或 `context` (in measurements) JSONB 欄位中。

---

## 3. 現狀診斷：關鍵缺陷 (Critical Gap Analysis)

在深入審計 `backend/app/schemas/__init__.py` 與 `data-engine/src/field_extractor.py` 後，辨識出以下三個關鍵缺陷：

### 🔴 Gap A：被「定義但未映射」的資料遺失風險 (Field Attrition)
*   **發現：** 當使用者在 Schema 中定義了欄位但 `target_column` 留空 (None) 時，萃取引擎 (FieldExtractor) 雖能抓到值並標記為 `is_schema_defined=True`，但因為缺乏明確的寫入指令，這些資料在進入資料庫前會無聲無息地消失。
*   **後果：** 導致使用者定義了 Schema 卻在 DB 找不到資料。

### 🔴 Gap B：後端驗證邏輯過於僵硬 (Rigid Backend Validation)
*   **發現：** 後端的 Pydantic 模型（SchemaTypeCreate/Update）將 `target_column` 限制在一組寫死的清單中，且不允許將欄位映射至 `details` 或 `context`。
*   **後果：** 剝奪了專家對資料流的主動控制權，無法明確指定哪些細節應進入 JSONB，強迫系統只能依賴被動的「自動捕捉」。

### 🔴 Gap C：DBWriter 缺乏統一的「打包溢位袋」邏輯
*   **發現：** 目前的寫入邏輯尚未標準化如何彙整所有「溢位」欄位（Overflow Fields）。
*   **後果：** 實作不一致可能導致自動捕捉到的「遺珠」資料與手動定義的細節資料無法正確合併存入 JSONB。

---

## 4. 改善建議與技術方案 (Strategic Recommendations)

### 4.1 後端：釋放 Mapping 限制
修改 `backend/app/schemas/__init__.py`，將 `details` 與 `context` 加入各類別的 `allowed_targets`。這讓 Schema 定義具備「主動溢位」的能力。

### 4.2 萃取引擎：強化溢位語義
優化 `FieldExtractor`，統一標記以下三類資料點為 `overflow=True`：
1.  手動定義映射至 `details`/`context` 的欄位。
2.  手動定義但 `target_column` 為空的欄位。
3.  Payload 中自動捕捉到的「遺珠」欄位 (Unknown fields)。

### 4.3 寫入引擎：實作自動打包器
在 `DBWriter` 執行 `INSERT` 前，將所有 `overflow=True` 的欄位彙整成一個 Python Dictionary，確保它們被安全地存入資料庫的 JSONB 容器中。

---

## 5. 後續實作路徑圖 (Implementation Roadmap)

| 階段 | 任務說明 | 目標解決 |
| :--- | :--- | :--- |
| **Phase 1: Backend** | 修改 Pydantic 驗證器，允許 `details/context` 映射。 | **Gap B** |
| **Phase 2: Extractor** | 修改 `FieldExtractor` 邏輯，明確標記 `overflow` 狀態。 | **Gap A** |
| **Phase 3: DBWriter** | 實作寫入前的 JSONB 彙整與打包功能。 | **Gap C** |
| **Phase 4: Validation** | 建立 `RecipeEvent` 示範，驗證所有動態欄位正確進入 `details`。 | **全系統驗證** |

---

**核准備忘錄：**
本報告確立了 UNS Platform 處理多樣化工業資料的標準路徑：**「語義分類為本，核心欄位優先，其餘自動溢位」**。這將確保系統在無需頻繁變更資料庫 Schema 的前提下，具備支援任何廠牌設備資料的能力。

**報告撰寫人：** Gemini CLI (Expert Agent)
**日期：** 2026-03-11
