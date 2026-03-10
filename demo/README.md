# UNS Platform Demo Data Seeding Guide

本指南說明如何為 UNS Platform 進行展示數據注入（Seeding），包含主數據初始化、ISA-95 層級結構設定以及即時數據模擬。

## 快速啟動 (One-Command Start)

如果您已經啟動了基礎設施（EMQX, TimescaleDB）與 Backend，可以直接執行：

```bash
./demo/run_demo.sh
```

該腳本會自動完成：
1. 注入 Master Data (E10 狀態、ISA-88 事件碼)。
2. 建立 ISA-95 命名空間 (TaiwanPrecision > Taoyuan > SMT)。
3. 配置數據過濾與儲存的 JSON Schema。
4. 啟動背景模擬器發送即時 Telemetry 數據。

---

## 數據注入的三個階段

### 1. Stage 1: Master Data (主數據)
*   **用途**: 定義系統通用的代碼表，如設備狀態碼、品質原因、生產事件。
*   **指令**: `bash ops/seed_namespace.sh` (前半段 SQL)
*   **核心內容**:
    *   `equipment_state`: PRD/RUN, SBY/IDL, UDT/ALM...
    *   `production_lifecycle_code`: LOT_START, UNIT_IN, UNIT_OUT, LOT_END...

### 2. Stage 2: Identity & Schema (身分與結構)
*   **用途**: 建立企業架構並定義各 Topic 接收數據的格式。
*   **腳本**: `demo/seed_data.py`
*   **核心內容**:
    *   建立節點：`TaiwanPrecision/Taoyuan/Line1/Printer`
    *   定義 Schema：Telemetry (溫度、壓力)、Event (Lot ID, Result)

### 3. Stage 3: Life Data Simulation (動態模擬)
*   **用途**: 模擬現場機台或 MES 持續發送數據到 MQTT Broker。
*   **腳本**:
    *   `demo/publish_data.py`: 持續發送基礎遙測數據。
    *   `demo/smart_factory_sim.py`: 支援更複雜的場景（如 `lifecycle` 完整批次流程）。

---

## 驗證數據流程

1. **MQTT 接收**: 使用 MQTTX 或 `mosquitto_sub` 訂閱 `TaiwanPrecision/#`。
2. **Backend 處理**: 查看 Backend 日誌，確認 Data Engine 是否成功 Match Schema。
3. **資料庫儲存**:
    ```sql
    SELECT * FROM ts_telemetry ORDER BY time DESC LIMIT 10;
    ```
4. **前端呈現**: 開啟 Tag Overview 頁面，查看節點樹與對應的標籤數值。

> [!TIP]
> 如果需要重置所有數據，請先執行 `bash ops/reset_db.sh`。
