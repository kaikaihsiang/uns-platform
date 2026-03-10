# UNS Platform 專業級驗證計畫 (V2 - 完整生命週期版)

本計畫基於工業實務（SEMI E10, IPC-CFX, ISA-95/88）設計，旨在通過高保真模擬驗證 UNS Platform 的數據流與主數據強化（Master Data Enrichment）邏輯。

---

## 1. 專業主數據定義 (Comprehensive Master Data)

所有資料需預先透過 `ops/seed_namespace.sh` 注入。

### 1.1 設備狀態 (SEMI E10 Standard)
| Category | Code | Sub Code | Label | Description |
|---|---|---|---|---|
| `equipment_state` | `PRD` | `RUN` | Productive - Running | 正常生產中 |
| `equipment_state` | `PRD` | `SET` | Productive - Setup | 換線/調機中 |
| `equipment_state` | `SBY` | `IDL` | Standby - Idle | 閒置（無工單） |
| `equipment_state` | `UDT` | `ALM` | Unscheduled Down - Alarm | 異常停機 |
| `equipment_state` | `SDT` | `MNT` | Scheduled Down - Maint | 計畫性保養 |

### 1.2 生產事件生命週期 (ISA-88/IPC-CFX)
| Category | Code | Label | Description |
|---|---|---|---|
| `production_lifecycle_code` | `LOT_DISPATCHED` | Lot Dispatched | 工單/批次下發 |
| `production_lifecycle_code` | `RECIPE_DOWNLOAD` | Recipe Download | 配方下載完成 |
| `production_lifecycle_code` | `MATERIAL_LOAD` | Material Loaded | 物料上機 (Reel/Feeder) |
| `production_lifecycle_code` | `LOT_START` | Lot Started | 批次生產正式啟動 |
| `production_lifecycle_code` | `UNIT_IN` | Unit In (Board In) | 工件/板件 進入機台 |
| `production_lifecycle_code` | `UNIT_OUT` | Unit Out (Board Out) | 工件/板件 移出機台 |
| `production_lifecycle_code` | `LOT_END` | Lot Ended | 批次生產結束 |
| `production_lifecycle_code` | `MATERIAL_UNLOAD` | Material Unloaded | 物料退機 |

### 1.3 告警代碼 (ISA-18.2 Severity)
| Category | Code | Label | Severity | Description |
|---|---|---|---|---|
| `alarm_code` | `E-VAC-001` | Vacuum Failed | Critical | 真空幫浦失效 |
| `alarm_code` | `E-VIB-022` | Spindle High Vib | Warning | 主軸振動預警 |
| `alarm_code` | `E-COM-999` | Comm Lost | Emergency | 通訊完全中斷 |

---

## 2. 數據格式規格 (Payload Standard Spec)

所有場景必須遵循 `docs/payload_standard_spec.md` 定義之信封格式。

### 2.1 標準信封 (_meta)
```json
{
  "_meta": {
    "category": "Telemetry | Status | Alarm | Event | Metrics",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/Mounter1",
    "timestamp": "ISO-8601-Format",
    "quality": "good"
  },
  "data": { ... }
}
```

---

## 3. 六大場景深度定義 (Scenario Deep Dive)

### 場景 1: Telemetry (多值遙測)
- **模擬 Payload**:
```json
"data": {
  "values": { "temp": 42.5, "vib": 0.85, "press": 0.52 },
  "units": { "temp": "°C", "vib": "mm/s", "press": "kPa" }
}
```
- **驗證**: `ts_telemetry` 是否依據 `values` 展開儲存。

### 場景 2: Status (狀態變遷)
- **模擬 Payload**:
```json
"data": {
  "state": "PRD", "sub_state": "SET", "mode": "auto",
  "reason_code": "CHANGE_OVER", "since": "..."
}
```
- **驗證**: `ts_status` 記錄 `sub_state`="SET"，且 `state` 與主數據對應。

### 場景 3: Alarms (告警生命週期)
- **模擬 Payload**:
```json
"data": {
  "alarm_id": "ALM-001", "code": "E-VAC-001",
  "severity": "critical", "message": "Low Vacuum", "state": "active"
}
```
- **驗證**: `ts_alarms` 記錄代碼與等級，且 `state` 正確反映 active。

### 場景 4: Events (生產流生命週期)
- **模擬 Payload (以 UNIT_IN 為例)**:
```json
"data": {
  "event_code": "UNIT_IN", "event_id": "EVT-101",
  "lot_id": "LOT-A", "unit_id": "PCB-001"
}
```
- **驗證**: 測試從 `LOT_DISPATCHED` 到 `LOT_END` 的完整時序能否在 `ts_events` 正確呈現。

### 場景 5: Measurements (量測/品質)
- **模擬 Payload**:
```json
"data": {
  "sample_id": "PCB-001", "sample_position": "U12",
  "value": 0.015, "result": "pass"
}
```
- **驗證**: `ts_measurements.sample_id` 是否正確填充。

### 場景 6: Metrics (KPI 統計)
- **模擬 Payload**:
```json
"data": {
  "metric_type": "OEE", "period": "shift",
  "values": { "oee": 88.5, "avail": 92.0, "perf": 96.0, "qual": 99.8 }
}
```
- **驗證**: `ts_metrics` 資料寫入且 `values` 包含完整 JSON。

---

## 4. 驗證工具開發計畫

### 4.1 `ops/seed_namespace.sh` 更新
- 擴充 `INSERT` 語句至 20+ 筆主數據。
- 配置 6 套對應上述格式的 `uns_payload_schemas`。

### 4.2 `demo/run_test.sh` 介面
```bash
./demo/run_test.sh lifecycle    # 執行完整生產週期模擬 (Scenarios 4, 5)
./demo/run_test.sh stability    # 執行持續遙測與狀態變遷 (Scenarios 1, 2)
./demo/run_test.sh maintenance  # 執行告警與維護統計 (Scenarios 3, 6)
```
