# ADR-004: 增強資料引擎快取一致性與系統強健性 (System Robustness)

## 狀態 (Status)
**Proposed / Technical Debt** (建議提案 / 技術債記錄)

## 背景 (Context)
在 UNS 平台開發過程中，觀測到當資料庫執行重置（如 `TRUNCATE`）但資料引擎（Data Engine）程序未重啟時，會引發嚴重的寫入錯誤。

### 問題定義 (Problem Definition)
資料引擎為了效能考量，在記憶體中維護了 `MQTT Topic → tag_id` 的映射快取（`TagLookup`）。當資料庫狀態發生劇烈變更（如手動刪除資料、恢復備份、或執行 `reset_db.sh`）時，資料引擎的記憶體快取會與資料庫實際狀態脫節（Stale Cache），導致後續的資料寫入因違反外鍵條件約束（Foreign Key Constraint Violation）而失敗。

### 根本原因分析 (Root Cause)
1.  **單向同步**：目前快取僅在啟動或「找不到 ID」時才向資料庫查詢，缺乏「主動失效 (Invalidation)」機制。
2.  **ID 不一致**：資料庫重置後，若 Sequence 未歸零或資料表重建，原有的 `tag_id` 在資料庫中已不存在。
3.  **無感失敗**：`DBWriter` 在批次寫入失敗時雖有 log 記錄，但無法回饋給 `Pipeline` 觸發快取更新。

## 風險評估 (Risks)
1.  **資料遺失**：一旦快取失效，受影響的 Topic 資料將持續寫入失敗，直到服務重啟。
2.  **維運成本高**：系統無法自我修復（Self-healing），高度依賴人工干預（重啟程序）。
3.  **系統脆裂性**：在不穩定的網路或資料庫維護情境下，系統表現不夠穩健，容易產生連鎖錯誤。

## 建議優化方案 (Proposed Solutions)

### 方案 A：實作自我修復快取 (Self-Healing Cache)
*   **機制**：修改 `DBWriter` 與 `Pipeline` 的互動模式。當發生外鍵衝突（Postgres Error `23503`）時，捕獲例外並識別出失效的 `tag_id`。
*   **動作**：自動清空 `TagLookup` 中對應的快取條目，並觸發立即重新建立（Re-register），最後重新嘗試寫入。
*   **優點**：無需外部依賴，純軟體邏輯達成。

### 方案 B：Postgres `LISTEN / NOTIFY` 即時失效機制
*   **機制**：在資料庫端建立 Trigger 或在管理腳本中發出 `NOTIFY cache_invalidation` 訊號。
*   **動作**：資料引擎啟動一個背景監聽程序，收到訊號後立即執行 `cache.clear()`。
*   **優點**：架構優雅，能達成接近即時的同步，對資料庫效能影響極小。

### 方案 C：導入資料庫紀元 (Database Epoch/Generation ID)
*   **機制**：在資料庫中儲存一個唯一的 `db_uuid` 或 `epoch_count`。
*   **動作**：資料引擎每次批次寫入前校驗記憶體中的 `epoch` 是否與資料庫一致。
*   **優點**：適用於大規模分散式環境，能防止程序連接到錯誤的資料庫實例（Instance）。

## 預期效果 (Expected Outcome)
*   **高可用性**：系統能在資料庫異常恢復後自動復歸，無需人工重啟。
*   **資料完整性**：大幅降低因快取過時導致的寫入失敗率。
*   **開發體驗**：開發者在執行測試或重置環境時，無需擔心服務間的狀態同步問題。

---
**紀錄日期**：2026-03-09  
**紀錄人**：Gemini CLI (Yokogawa DX Consultant Mode)
