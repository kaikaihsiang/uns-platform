# UNS Payload 標準規格 (ISA-95 L0–L4)

## 概述

本文件定義 UNS 系統中 MQTT Payload 的標準格式，分為三大區塊：

| 區塊 | 適用層級 | 標準化程度 | 說明 |
|---|---|---|---|
| **Part A：標準 Payload** | L0–L2 | ✅ **嚴格標準** | Telemetry / Status / Alarm — 格式完全固定，所有設備必須遵循 |
| **Part B：信封 + 自定義** | L2–L4 | 📨 **僅信封標準** | Event / Metrics / Command / Config / Batch / MasterData — `_meta` 固定，`data` 由各系統自行定義 |
| **Part C：交握機制 (ACK)** | L2–L4 | 🤝 **通訊協議** | 需要確認送達的 Category 必須實作 correlation_id + reply_to + timeout 交握 |

> **為什麼分兩塊？** L0-L2 是物理世界（溫度就是 float + 單位），可以統一。L2 以上是業務邏輯（每間工廠的工單、配方、BOM 都不同），只能統一信封格式，內容無法也不應該強制標準化。

---

## 信封格式 (_meta)

**所有 Payload（Part A + Part B）都必須包含此信封結構，欄位定義固定不變。**

```json
{
  "_meta": {
    "category":  "Telemetry",
    "schema_version": "1.0",
    "source":    "TaiwanPrecision/Taoyuan/SMT/Line1/Printer",
    "timestamp": "2024-01-15T08:30:00.000+08:00",
    "quality":   "good"
  },
  "data": { }
}
```

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `category` | string | ✅ | Part A 的 3 種 或 Part B 的 6 種類別 |
| `schema_version` | string | ✅ | Schema 版本號（語義化版本） |
| `source` | string | ✅ | 發送端的 topic 路徑前綴 |
| `timestamp` | string (ISO 8601) | ✅ | 資料產生時間（含時區） |
| `quality` | string | ⬡ | 資料品質：`good` / `uncertain` / `bad`，預設 `good` |
| `correlation_id` | string | ⬡ | 交握用唯一 ID（需要 ACK 的 Category 為必填，見 Part C） |
| `reply_to` | string | ⬡ | 指定回覆 Topic（僅 Request 端填寫） |
| `is_response` | boolean | ⬡ | 標記此訊息為回應（僅 Response 端填寫） |

---

# Part A：標準 Payload（L0–L2）

> **這三種格式是嚴格標準。所有設備接入 UNS 時，必須將資料轉換為以下格式。
> 若設備本身無法輸出標準格式，應由 Edge Gateway 負責轉換。**

---

## 1. Telemetry（遙測數據）

**用途**：感測器即時數值回報（溫度、壓力、速度、電流…）

**特性**：高頻率（毫秒~秒級）、QoS 0、不 Retain

### 單值遙測

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/Temperature`

```json
{
  "_meta": {
    "category": "Telemetry",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/Printer",
    "timestamp": "2024-01-15T08:30:00.000+08:00",
    "quality": "good"
  },
  "data": {
    "value": 25.3,
    "unit": "°C"
  }
}
```

### 多值遙測

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Telemetry/ZoneTemps`

```json
{
  "_meta": {
    "category": "Telemetry",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven",
    "timestamp": "2024-01-15T08:30:00.000+08:00",
    "quality": "good"
  },
  "data": {
    "values": {
      "zone1_temp": 179.5,
      "zone2_temp": 219.8,
      "zone3_temp": 260.2,
      "conveyor_speed": 0.8
    },
    "units": {
      "zone1_temp": "°C",
      "zone2_temp": "°C",
      "zone3_temp": "°C",
      "conveyor_speed": "m/min"
    }
  }
}
```

### data 欄位規格（嚴格標準）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `value` | number | ✅ (單值) | 感測值 |
| `unit` | string | ✅ (單值) | 工程單位 |
| `values` | object | ✅ (多值) | key-value 對，每個 key 是數據點名稱 |
| `units` | object | ✅ (多值) | 與 values 對應的單位 |

---

## 2. Status（設備狀態）

**用途**：設備運行狀態回報

**特性**：狀態變更時發送、QoS 1、**必須 Retain**

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Status/MachineState`

```json
{
  "_meta": {
    "category": "Status",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/Printer",
    "timestamp": "2024-01-15T08:00:00+08:00",
    "quality": "good"
  },
  "data": {
    "state": "running",
    "sub_state": "producing",
    "mode": "auto",
    "since": "2024-01-15T08:00:00+08:00"
  }
}
```

### data 欄位規格（嚴格標準）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `state` | string enum | ✅ | `running` / `idle` / `changeover` / `maintenance` / `fault` / `offline` |
| `sub_state` | string | ⬡ | 細分狀態（如 `producing` / `warming_up`） |
| `mode` | string enum | ✅ | `auto` / `manual` / `semi_auto` |
| `since` | string (ISO 8601) | ⬡ | 進入此狀態的時間 |

> **`state` 的 6 種枚舉值是固定的**，不可自行新增。這確保所有設備的狀態語義一致，Consumer 可以統一處理（如計算 OEE 的 Availability）。

---

## 3. Alarm（告警）

**用途**：設備告警、製程異常通知

**特性**：不定期、QoS 1、Retain（顯示當前有效告警）

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Alarm/ActiveAlarms`

```json
{
  "_meta": {
    "category": "Alarm",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven",
    "timestamp": "2024-01-15T09:15:00+08:00",
    "quality": "good"
  },
  "data": {
    "alarm_id": "ALM-2024-0115-001",
    "code": "REFLOW-T01",
    "severity": "critical",
    "message": "迴焊區溫度超過上限值 (265°C > 262°C)",
    "source_tag": "Zone3.Temperature",
    "current_value": 265.0,
    "threshold": 262.0,
    "unit": "°C",
    "state": "active"
  }
}
```

### data 欄位規格（嚴格標準）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `alarm_id` | string | ✅ | 唯一告警 ID |
| `code` | string | ✅ | 告警代碼（設備定義，不強制統一） |
| `severity` | string enum | ✅ | `info` / `warning` / `critical` / `emergency` |
| `message` | string | ✅ | 人類可讀的告警說明 |
| `source_tag` | string | ⬡ | 觸發來源的 tag |
| `current_value` | number | ⬡ | 觸發時的數值 |
| `threshold` | number | ⬡ | 閾值 |
| `unit` | string | ⬡ | 單位 |
| `state` | string enum | ✅ | `active` / `cleared` / `shelved` |

> **`severity` 的 4 種枚舉值依循 ISA-18.2 告警管理標準。**
>
> **告警確認（Acknowledge）不在此 payload 中處理。** 設備只負責發送告警觸發（`active`）與解除（`cleared`），
> 確認操作由 AMS（告警管理系統）自行管理 — 操作員在 SCADA/HMI 確認後，AMS 在自己的 DB 記錄 `acknowledged_by` / `acknowledged_at`，
> 不需要 re-publish 回 MQTT。

---

## Part A Consumer 實作

基於以上 3 種標準格式，統一 Consumer 只需 3 個 handler：

```python
import json

def on_message(topic, payload_bytes):
    msg = json.loads(payload_bytes.decode("utf-8"))
    meta = msg["_meta"]
    data = msg["data"]

    if meta["category"] == "Telemetry":
        # data 一定有 value+unit 或 values+units → 直接存時序 DB
        store_timeseries(topic, meta["timestamp"], data)

    elif meta["category"] == "Status":
        # data 一定有 state+mode → 更新設備狀態表
        update_device_state(topic, data["state"], data["mode"])

    elif meta["category"] == "Alarm":
        # data 一定有 severity+message → 推播通知
        if data["severity"] in ("critical", "emergency"):
            send_alert(data["message"], data["severity"])
        store_alarm(topic, data)
```

**這 3 個 handler 可以無修改地處理工廠裡所有設備的基礎資料。**

---

# Part B：信封 + 自定義 Payload（L2–L4）

> **以下 6 種類別只規範信封格式（`_meta`），`data` 的內容由各系統介面自行定義。
> UNS 系統的角色是「郵局」 — 收發、歸檔、追蹤 schema 變化，不規定信的內容。**

---

## 4. Event（製程事件）

**用途**：記錄製程中離散發生的事件，如 AOI 檢測完成、換線、物料上機

**QoS 1 / 不 Retain**

### 信封結構（固定）+ data 最低要求

**Topic**: `TaiwanPrecision/Taoyuan/QualityControl/Inspection1/AOI/Event/InspectionResult`

```json
{
  "_meta": {
    "category": "Event",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/QualityControl/Inspection1/AOI",
    "timestamp": "2024-01-15T08:35:00+08:00",
    "quality": "good"
  },
  "data": {
    "event_code": "inspection_complete",
    "event_id": "EVT-2024-0115-0042"
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `event_code` | ✅ | 事件類型識別符（各系統自行定義） |
| `event_id` | ✅ | 唯一事件 ID |
| 其他欄位 | ⬡ | **自定義** — 依各系統需求自行加入 |

### 範例：不同系統的 Event data 長得完全不同

```json
// Topic: .../QualityControl/Inspection1/AOI/Event/InspectionResult
"data": {
  "event_code": "inspection_complete",
  "event_id": "EVT-001",
  "board_serial": "PCB-001",
  "result": "NG",
  "defects": [{"type": "solder_bridge", "component": "U3"}]
}

// Topic: .../SMT/Line1/Event/Changeover
"data": {
  "event_code": "changeover_complete",
  "event_id": "EVT-002",
  "from_product": "PCB-A001",
  "to_product": "PCB-B002",
  "duration_min": 25
}
```

> **UNS 系統不需要理解 data 裡的 defects 或 duration_min — 它只需存下來、推斷 schema、追蹤變化。**

---

## 5. Metrics（計算指標）

**用途**：OEE、良率、MTBF 等經計算的指標

**QoS 1 / Retain**

### 信封 + 最低要求

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/Metrics/OEE`

```json
{
  "_meta": {
    "category": "Metrics",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1",
    "timestamp": "2024-01-15T12:00:00+08:00",
    "quality": "good"
  },
  "data": {
    "metric_type": "OEE",
    "period": "current_shift",
    "values": {
      "availability": 0.92,
      "performance": 0.88,
      "quality": 0.984,
      "oee": 0.797
    }
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `metric_type` | ✅ | 指標類型（各系統自定義：`OEE`, `yield`, `MTBF`…） |
| `period` | ✅ | 計算區間 |
| `values` | ✅ | 指標數值（key-value） |
| 其他欄位 | ⬡ | **自定義** — 如 losses 明細、context 等 |

---

## 6. Command（控制指令）

**用途**：從上位系統下發控制指令

**QoS 1 / 不 Retain**

### 信封 + 最低要求

```json
// Request — Topic: TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Command/Control
{
  "_meta": { "category": "Command", ... },
  "data": {
    "request_id": "CMD-001",
    "action": "set_parameter",
    "requested_by": "OP-001"
  }
}

// Response — Topic: TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Command/Ack
{
  "_meta": { "category": "Command", ... },
  "data": {
    "request_id": "CMD-001",
    "status": "accepted"
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `request_id` | ✅ | 唯一請求 ID（配對 Request/Response） |
| `action` | ✅ | 指令動作（各設備自定義） |
| `requested_by` | ✅ | 請求者 ID |
| `status` (Response) | ✅ | `accepted` / `rejected` / `error` / `timeout` |
| 其他欄位 | ⬡ | **自定義** — 如 parameters, reason 等 |

---

## 7. Config（配方 / 參數設定）

**用途**：配方下載、製程參數設定

**QoS 1 / Retain**

### 信封 + 最低要求

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Config/Download`

```json
{
  "_meta": { "category": "Config", ... },
  "data": {
    "config_type": "recipe",
    "config_id": "RCP-REFLOW-A001-R3",
    "config_version": "3.2",
    "name": "PCB-A001-Rev3 迴焊參數"
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `config_type` | ✅ | `recipe` / `threshold` / `calibration` / 自定義 |
| `config_id` | ✅ | 配方唯一 ID |
| `config_version` | ✅ | 版本號 |
| `name` | ✅ | 人類可讀名稱 |
| 其他欄位 | ⬡ | **自定義** — parameters, approved_by 等由各系統定義 |

---

## 8. Batch（批次生命週期）

**用途**：追蹤批次/工單的生命週期

**QoS 1 / 不 Retain**

### 信封 + 最低要求

**Topic**: `TaiwanPrecision/Taoyuan/SMT/Line1/Batch/Control`

```json
{
  "_meta": { "category": "Batch", ... },
  "data": {
    "lifecycle_state": "started",
    "batch_id": "B-2024-0115-001",
    "work_order": "WO-2024-0042"
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `lifecycle_state` | ✅ | `started` / `in_progress` / `paused` / `completed` / `aborted` |
| `batch_id` | ✅ | 批次唯一 ID |
| `work_order` | ✅ | 工單號 |
| 其他欄位 | ⬡ | **自定義** — product_id, recipe_id, material_lots 等由 MES 定義 |

---

## 9. MasterData（主資料 / ERP 同步）

**用途**：從 ERP 同步工單、BOM、物料主檔

**QoS 1 / Retain**

### 信封 + 最低要求

**Topic**: `TaiwanPrecision/Taoyuan/MasterData/Sync`

```json
{
  "_meta": { "category": "MasterData", ... },
  "data": {
    "data_type": "work_order",
    "record_id": "WO-2024-0042",
    "action": "create"
  }
}
```

| 欄位 | 必填 | 說明 |
|---|---|---|
| `data_type` | ✅ | `work_order` / `bom` / `material` / `product` / 自定義 |
| `record_id` | ✅ | 紀錄唯一 ID |
| `action` | ✅ | `create` / `update` / `delete` |
| 其他欄位 | ⬡ | **完全自定義** — 每間公司的 ERP 資料結構都不一樣 |

---

## Part B Consumer 實作

Part B 的 Consumer 分兩層：

```python
def on_message(topic, payload_bytes):
    msg = json.loads(payload_bytes.decode("utf-8"))
    meta = msg["_meta"]
    data = msg["data"]
    category = meta["category"]

    # ═══════════════════════════════════════════════
    # 通用層（UNS Manager 負責）— 不需要理解 data 內容
    # ═══════════════════════════════════════════════
    store_raw(topic, meta["timestamp"], category, data)     # 存原始資料
    track_schema(topic, category, data)                      # 追蹤 schema 變化
    log_event(topic, category, meta["timestamp"])            # 記錄事件日誌

    # ═══════════════════════════════════════════════
    # 應用層（各系統各自實作）— 需要理解 data 內容
    # ═══════════════════════════════════════════════
    # 這一層由各部門/系統自行開發，不在 UNS 標準範圍內
    # 例如：
    #   - MES 系統訂閱 Batch/* 處理批次邏輯
    #   - 品質系統訂閱 Event/InspectionResult 處理 SPC
    #   - ERP 介面訂閱 MasterData/* 同步工單
    app_handler = APPLICATION_HANDLERS.get(category)
    if app_handler:
        app_handler.process(topic, meta, data)
```

---

## 總結：UNS 系統的角色定位

```
              你的 UNS Namespace Manager 的職責

  Part A (L0-L2)                Part B (L2-L4)
  ┌─────────────────┐          ┌─────────────────┐
  │ 規範制定者       │          │ 郵局            │
  │                 │          │                 │
  │ • 定義標準格式   │          │ • 統一信封      │
  │ • 驗證合規性     │          │ • 收發歸檔      │
  │ • 統一 Consumer │          │ • 追蹤 schema   │
  │ • 拒絕不合規     │          │ • 不管信的內容   │
  └─────────────────┘          └─────────────────┘
  3 種固定格式                  6 種信封 + 自定義
  所有設備必須遵循              各系統自行定義 data
```

---

## 版本演進策略

| 變更類型 | `schema_version` | Consumer 處理 |
|---|---|---|
| 新增選填欄位（相容） | `1.0` → `1.1` | 忽略未知欄位 |
| 欄位改名/刪除（不相容） | `1.x` → `2.0` | 檢查 major version |

```python
def is_compatible(schema_version):
    major = int(schema_version.split(".")[0])
    return major == 1  # 目前 Consumer 支援 v1.x
```

---

# Part C：L2-L4 系統間通訊策略

> **⚠️ 架構決策：L2-L4 的 Request/Response 交易不使用 MQTT。**
>
> 經過設計評估，MQTT 的 pub/sub 模式不適合處理需要確認回應的跨系統交易
>（如 LotMoveIn、配方下載、指令執行）。在 MQTT 上用 `correlation_id` + `reply_to` + `timeout`
> 模擬 RPC 是**反模式** — 本質上是用 pub/sub 假裝 request/response。
>
> **本架構採用 MQTT + gRPC 雙協議策略：**
> - **MQTT**：L0-L2 event-driven 資料（Telemetry/Status/Alarm/Event/Metrics）
> - **gRPC**：L2-L4 request/response 交易（Command/Config/Batch/MasterData/Query）

---

## 協議選型總覽

| Category | 資料性質 | 協議 | 原因 |
|---|---|---|---|
| Telemetry | 事件驅動（有事發生了） | **MQTT** | pub/sub 天生適合 |
| Status | 事件驅動 | **MQTT** | Retained message 保證最新值 |
| Alarm | 事件驅動 | **MQTT** | 告警觸發/解除是事件 |
| Event | 事件驅動 | **MQTT** | 製程事件通知 |
| Metrics | 事件驅動 | **MQTT** | 定期發佈指標 |
| **Command** | 請求/回應（幫我做事） | **gRPC** | 指令需要確認執行結果 |
| **Config** | 請求/回應 | **gRPC** | 配方下載需要確認載入 |
| **Batch** | 請求/回應 | **gRPC** | 批次操作需要確認狀態 |
| **MasterData** | 請求/回應 | **gRPC** | 資料同步需要確認接收 |
| **Query** | 請求/回應 | **gRPC** | 查詢歷史/聚合資料 |

### 為什麼 gRPC 比 MQTT ACK 更適合？

| 面向 | MQTT ACK（模擬 RPC） | gRPC（原生 RPC） |
|---|---|---|
| 合約定義 | JSON + 人工文件 | `.proto` 檔案（編譯器驗證） |
| 回應機制 | 自己做 correlation_id + reply_to | **語言層面直接 return** |
| 超時處理 | 自己做 timer + retry | **gRPC deadline 內建** |
| 錯誤處理 | 自己定義 error 格式 | **gRPC status code 標準** |
| 型別安全 | 無（runtime 才知道格式錯） | **編譯期就知道** |
| Code gen | 無 | **protoc 自動產生 client/server** |

---

## Command-Event 分離模式

L3-L4 系統執行交易時，採用 **Command-Event Separation**：

```
Command（做事）：  Client ──gRPC──► Service ──► DB       ← Source of Truth
                                     │
Event  （廣播）：                     └──MQTT──► UNS     ← 即時通知 + 歷史紀錄
```

- **gRPC 負責「做事」**（交易、指令、確認）— response 就是 ACK
- **MQTT 負責「廣播結果」**（告訴全世界發生了什麼）— 事後通知

### LotMoveIn 完整流程

```
  OPI (操作員介面)         MES Service              UNS
  ┌────────────┐         ┌──────────────┐         ┌──────────────┐
  │ 1. 按鈕     │──gRPC──►│ 2. 商業邏輯   │         │ MQTT Broker  │
  │   LotMoveIn │         │  - 檢查設備   │         │              │
  │             │         │  - 驗證配方   │         │              │
  │             │         │ 3. 寫 MES DB  │         │              │
  │             │◄─gRPC───│ 4. 回應 OK    │         │              │
  │ 5. 顯示成功 │         │              │         │              │
  │             │         │ 6. Publish    │──MQTT──►│ 7. 廣播事件  │
  │             │         │    Event      │         │  → Dashboard │
  │             │         │              │         │  → TimescaleDB│
  │             │         │              │         │  → 品質系統   │
  └────────────┘         └──────────────┘         └──────────────┘
```

### gRPC 的 response 就是 ACK

```protobuf
// batch_service.proto

service BatchService {
    rpc LotMoveIn (LotMoveInRequest) returns (LotMoveInResponse);
    rpc LotMoveOut (LotMoveOutRequest) returns (LotMoveOutResponse);
}

message LotMoveInRequest {
    string lot_id = 1;
    string equipment_id = 2;
    string recipe_id = 3;
    string operator_id = 4;
}

message LotMoveInResponse {
    bool success = 1;          // true = ACK, false = NACK
    string lot_id = 2;
    string message = 3;
    string alarm_code = 4;     // 失敗時的錯誤代碼
}
```

**不需要 correlation_id、不需要 reply_to、不需要 Transaction Log、不需要 timeout/retry 邏輯。**
gRPC 的 HTTP/2 框架天生處理這些。

---

## MES 事件進入 UNS 的三種方式

MES 完成交易後，事件進入 MQTT/UNS 的方式：

| 方式 | MES 改動 | 可靠性 | 推薦場景 |
|---|---|---|---|
| 直接在 code 裡加 `mqtt.publish()` | 改幾行 | ⚠️ MQTT 發送失敗時丟失 | POC / Demo |
| **Outbox Pattern**（掃 event table） | 加一個 DB 欄位 | ✅ 不會丟 | **Production** |
| **CDC (Debezium)** | **零改動** | ✅ 不會丟 | **已有 MES 系統** |

### CDC (Debezium) — 推薦方式

**不需要改 MES 的任何一行程式碼。** 透過監聽 MES DB 的 WAL (Write-Ahead Log)，
自動捕捉 `event_tracking` 表的 INSERT，轉換成 UNS 信封格式發到 MQTT。

```
MES PostgreSQL → Debezium → Transform Service → MQTT Broker → UNS Consumer → TimescaleDB
                                  ↑
                        你唯一需要寫的：
                        MES DB row → UNS 信封的轉換規則
```

> **完整範例見 `examples/uns/cdc_mes_bridge/` 目錄。**

---

## 資料查詢架構 (Data Access Service)

L2-L4 系統查詢歷史資料時，透過 gRPC Data Access Service：

```
L2/L3/L4 系統 ──gRPC──► Data Access Service ──SQL──► TimescaleDB
                       （翻譯層：asset_path → tag_id → SQL 查詢）
```

呼叫端使用 `asset_path` + `data_point` 定位資料（業務語言），
Data Access Service 翻譯成 `tag_id` + 對應的 `ts_*` 表查詢。

### 查詢服務核心 API

```protobuf
service UNSQueryService {
    rpc BrowseAssets (BrowseRequest) returns (BrowseResponse);
    rpc ListTags (ListTagsRequest) returns (ListTagsResponse);
    rpc GetCurrentValue (TagRequest) returns (CurrentValueResponse);
    rpc QueryTelemetry (TelemetryQuery) returns (stream TelemetryPoint);
    rpc QueryStatusHistory (StatusQuery) returns (stream StatusRecord);
    rpc QueryAlarms (AlarmQuery) returns (stream AlarmRecord);
    rpc QueryEvents (EventQuery) returns (stream EventRecord);
    rpc QueryMetrics (MetricsQuery) returns (stream MetricsRecord);
}
```

---

## MQTT 可靠性策略（僅適用 L0-L2 event-driven 資料）

### 各 Category 的可靠性需求

| Category | 丟失影響 | 策略 |
|---|---|---|
| Telemetry | 低（高頻，丟一筆無影響） | QoS 0，不做特殊處理 |
| Status | 中（但可恢復） | QoS 1 + **Retained message** |
| Alarm | 高（告警必須送達） | QoS 1 + Retained |
| Event | 中 | QoS 1 |
| Metrics | 低（週期性覆蓋） | QoS 1 + Retained |

### Consumer 離線問題

MQTT Broker 不是 Queue — Consumer 離線時訊息丟失。

**L0-L2 的處理方式：**
- **Telemetry**：丟就丟，高頻資料丟一筆無影響
- **Status**：Retained message 保證 Consumer 上線時拿到最新狀態
- **Alarm**：Retained message 保證最新告警狀態

**L3-L4 的處理方式：**
- 走 gRPC，不走 MQTT，沒有 Consumer 離線問題
- MES 事件透過 CDC (Debezium) 進入 UNS，CDC 有自己的 offset 管理，不會丟失

### HA（高可用）多實例支援

```
# MQTT 5.0 Shared Subscription
# 多個 UNS Consumer 實例共享訂閱，每筆訊息只處理一次

Consumer-1: SUBSCRIBE $share/uns-group/TaiwanPrecision/#
Consumer-2: SUBSCRIBE $share/uns-group/TaiwanPrecision/#
Consumer-3: SUBSCRIBE $share/uns-group/TaiwanPrecision/#

# Broker 對每筆訊息只送到其中一個 Consumer
```

### 冪等性（Idempotency）

Consumer 可能因為 QoS 1 重送而收到重複訊息。用 `_meta.timestamp` + `_meta.source` 做去重：

```python
def should_process(meta, last_processed):
    key = f"{meta['source']}:{meta['category']}"
    ts = meta["timestamp"]
    if key in last_processed and last_processed[key] >= ts:
        return False  # 已處理或更舊的資料
    last_processed[key] = ts
    return True
```


