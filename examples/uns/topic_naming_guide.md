# UNS Topic 命名規範指南

## 概述

此文件定義 MQTT Topic 的命名規範，確保整個 Unified Namespace 的一致性與可維護性。
所有開發人員與系統整合商在新增 Topic 時，**必須**遵循此規範。

---

## 命名格式

```
{企業}/{廠區}/{區域}/{產線}/{設備}/{類別}/{數據點}
```

每一層級對應 ISA-95 架構：

| 層級 | ISA-95 | 範例 | 說明 |
|---|---|---|---|
| 1 | Enterprise | `TaiwanPrecision` | 公司名稱或代號 |
| 2 | Site | `Taoyuan` | 廠區 / 工廠 |
| 3 | Area | `SMT` | 車間 / 區域 |
| 4 | Line | `Line1` | 產線 |
| 5 | Cell / Equipment | `Printer` | 設備或工作站 |
| 6 | Category | `Telemetry` | 數據類別 |
| 7 | Data Point | `Temperature` | 具體數據點 |

---

## 標準類別 (Category)

| 類別 | 用途 | QoS | Retain |
|---|---|---|---|
| `Telemetry` | 感測器數值（溫度、壓力、速度） | 0 | ❌ |
| `Status` | 設備運行狀態 | 1 | ✅ |
| `Alarm` | 告警訊息 | 1 | ✅ |
| `Event` | 製程事件（檢測結果、換線完成） | 1 | ❌ |
| `Command` | 控制指令（啟停、參數調整） | 1 | ❌ |
| `Config` | 配方 / 參數設定（ISA-88 配方下載） | 1 | ✅ |
| `Metrics` | 計算指標（OEE、良率、MTBF） | 1 | ✅ |
| `Batch` | 批次生命週期（開始 / 進行 / 結束） | 1 | ❌ |
| `MasterData` | 工單 / BOM / 物料主檔（ERP 同步） | 1 | ✅ |
| `Maintenance` | 維護紀錄（保養、耗材壽命） | 1 | ✅ |
| `Raw` | 未轉換的原始數據 | 0 | ❌ |

---

## ✅ 正確範例

```
# 遙測：SMT 產線一號印刷機的溫度
TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature

# 狀態：組裝線機器人的運行狀態
TaiwanPrecision/Taoyuan/Assembly/Line1/Robot1/Status/MachineState

# 告警：迴焊爐的有效告警清單
TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Alarm/ActiveAlarms

# 品質事件：AOI 檢測結果
TaiwanPrecision/Taoyuan/QualityControl/Inspection1/AOI/Event/InspectionResult

# OEE 指標：SMT 產線一即時 OEE
TaiwanPrecision/Taoyuan/SMT/Line1/Metrics/OEE

# 批次開始
TaiwanPrecision/Taoyuan/SMT/Line1/Batch/Start

# 維護：貼片機供料器壽命
TaiwanPrecision/Taoyuan/SMT/Line1/PickAndPlace/Maintenance/FeederLife
```

---

## ❌ 錯誤範例與修正

### 1. 扁平命名 — 缺少層級上下文

```
# ❌ 錯誤
sensors/temperature/001
machine_status/printer

# ✅ 修正
TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature
TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Status/MachineState
```

**為什麼錯**：無法從 topic 路徑判斷「這是哪個廠、哪條線、哪台設備」。

### 2. 數據值寫在 Topic 名稱裡

```
# ❌ 錯誤
factory/printer/temperature/25.3
factory/printer/status/running

# ✅ 修正
factory/printer/Telemetry/Temperature    → payload: {"value": 25.3}
factory/printer/Status/MachineState      → payload: {"state": "running"}
```

**為什麼錯**：Topic 是「地址」，Payload 是「內容」。把值放在 topic 裡會導致無法訂閱。

### 3. 混合用途的 Topic

```
# ❌ 錯誤：把感測值和控制指令放在同一個 topic
factory/printer/data
  → 有時發 {"temperature": 25.3}
  → 有時發 {"command": "start"}

# ✅ 修正：分開
factory/printer/Telemetry/Temperature
factory/printer/Command/Control
```

**為什麼錯**：訂閱方無法區分收到的是數據還是指令，容易導致邏輯錯誤。

### 4. 使用中文或特殊字元

```
# ❌ 錯誤
台灣精密/桃園廠/SMT/產線一/印刷機/溫度
factory/Line #1/printer (v2)/temp

# ✅ 修正
TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature
```

**為什麼錯**：中文和特殊字元在不同 MQTT client 的編碼處理不一致，容易出問題。

### 5. 沒有類別層 (Category)

```
# ❌ 錯誤
Factory/Taoyuan/SMT/Line1/Printer/Temperature
Factory/Taoyuan/SMT/Line1/Printer/MachineState

# ✅ 修正（加上類別層區分數據性質）
Factory/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature
Factory/Taoyuan/SMT/Line1/Printer/Status/MachineState
```

**為什麼錯**：沒有類別層就無法用 wildcard 批次訂閱，例如 `.../Printer/Telemetry/#` 訂閱所有遙測值。

---

## 命名慣例

| 規則 | 範例 | 說明 |
|---|---|---|
| 使用 PascalCase | `PickAndPlace` | 設備、類別名稱 |
| 避免底線和連字號 | ✅ `Line1` ❌ `line-1` | 保持簡潔 |
| 英文命名 | `Temperature` | 確保系統相容性 |
| 縮寫要一致 | `QC` 或 `QualityControl`，擇一 | 全廠統一 |
| 不超過 8 層 | — | 過深的層級不利管理 |

---

## Wildcard 訂閱模式

基於此命名規範，可以靈活訂閱：

```bash
# 桃園廠所有數據
TaiwanPrecision/Taoyuan/#

# SMT 區域所有溫度遙測
TaiwanPrecision/Taoyuan/SMT/+/+/Telemetry/Temperature

# 所有設備的告警
TaiwanPrecision/Taoyuan/+/+/+/Alarm/#

# 特定產線的所有數據
TaiwanPrecision/Taoyuan/SMT/Line1/#

# 所有廠區的 OEE 指標
TaiwanPrecision/+/+/+/Metrics/OEE
```
