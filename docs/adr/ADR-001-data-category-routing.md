# ADR-001: Data Category 路由機制 — Schema Type category vs Node category

> **狀態**：✅ Accepted  
> **日期**：2026-03-04  
> **決策者**：Kai-Hsiang (Product Owner / DX Strategist)  
> **影響範圍**：Data Engine Pipeline、Schema Types DB Schema、Namespace Nodes DB Schema、DBWriter

---

## 1. 背景與問題

Data Engine 從 MQTT 收到的 Raw Payload，經過 Schema 比對與欄位提取後，需要**依照資料的語義類型**，路由到不同的 TimescaleDB 目標表。

### 1.1 目標表清單

| 語義類型 (category) | 目標表 | 說明 | 典型欄位 |
|---|---|---|---|
| `telemetry` | `ts_telemetry` | 連續數值（溫度、壓力等） | `time, tag_id, value, value_text, quality` |
| `status` | `ts_status` | 設備狀態機轉換 | `time, tag_id, state, previous_state, duration_sec` |
| `alarm` | `ts_alarms` | 警報事件 | `time, tag_id, alarm_code, severity, message, acknowledged` |
| `event` | `ts_events` | 離散事件（LotMoveIn/Out 等） | `time, event_code, source_topic, payload, lot_id` |
| `measurement` | `ts_measurements` | 品質量測值（SPC 用） | `time, tag_id, value, spec_upper, spec_lower` |

### 1.2 Namespace Tree 與目標表的對應關係

根據 `platform_system_spec.md` §3.1，Namespace Tree 的 Topic Node 天然帶有語義：

```
Equipment
  ├── [Topic] Telemetry      → ts_telemetry
  ├── [Topic] Status         → ts_status
  ├── [Topic] Alarm          → ts_alarms
  ├── [Topic] Measurement    → ts_measurements
  └── [Topic] Event/{category} → ts_events
```

**核心問題**：這個「語義類型 (category)」應該定義在哪裡？誰來決定一筆 Payload 最終落到哪張表？

---

## 2. 評估的方案

### 2.1 方案 A：Topic 命名慣例

用 MQTT Topic 最末段名稱（`Telemetry` / `Status` / `Alarm`）自動推斷 category。

**機制**：
```python
# Data Engine 路由邏輯
topic = "TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry"
category = topic.split("/")[-1].lower()  # → "telemetry"
```

| 優點 | 缺點 |
|---|---|
| 零設定、零 DB 改動 | 命名不規範時直接壞掉 |
| 直覺簡單 | 無法處理自定義 Topic 名稱（如 `SensorData`） |
| | 依賴人為命名規範，不適合當主要機制 |

---

### 2.2 方案 B：Schema Type 加 `category` 欄位

在 `schema_types` 表新增 `category VARCHAR DEFAULT 'telemetry'`。  
Category 綁在 **Schema Type 級別**，全域一致。

**機制**：

以兩條 SMT 產線為例，每條各有一台 Printer：

```
Namespace Tree:
  TaiwanPrecision/Taoyuan/SMT/
    Line1/Printer/
      Telemetry    ← Topic Node
      Status       ← Topic Node
      Alarm        ← Topic Node
    Line2/Printer/
      Telemetry    ← Topic Node
      Status       ← Topic Node
```

Schema Type 定義（存在 `schema_types` 表裡）：

```yaml
Schema Type: "SMT_Printer_Telemetry"
  schema_category: "telemetry"          # ← 🔑 寫在 Schema 上
  fields:
    - {name: "temperature", type: "float", deadband: 0.5}
    - {name: "pressure",    type: "float", deadband: 0.05}

Schema Type: "SMT_Printer_Status"
  schema_category: "status"             # ← 🔑 寫在 Schema 上
  fields:
    - {name: "state",          type: "string", deadband: "change_only"}
    - {name: "previous_state", type: "string"}

Schema Type: "SMT_Printer_Alarm"
  schema_category: "alarm"              # ← 🔑 寫在 Schema 上
  fields:
    - {name: "alarm_code", type: "string"}
    - {name: "severity",   type: "integer"}
    - {name: "message",    type: "string"}
```

Namespace Node 綁定時：

```
Line1/Printer/Telemetry → schema_type = "SMT_Printer_Telemetry"  (category 跟著 Schema 走)
Line1/Printer/Status    → schema_type = "SMT_Printer_Status"     (category 跟著 Schema 走)
Line2/Printer/Telemetry → schema_type = "SMT_Printer_Telemetry"  (同一個 Schema，同一個 category)
```

**結果**：Category 和 Schema Type 是 1:1 綁死的。同一個 Schema Type 永遠只能寫到同一張表。

| 優點 | 缺點 |
|---|---|
| 簡單明確：定義 Schema 時就決定了目標表 | 不夠彈性：同 Schema 只能進同一張表 |
| 一致性高：100 台同型設備同一 Schema，保證全部寫到同一張表 | 特殊情境需複製 Schema（見下方範例） |
| Data Engine 路由邏輯簡單：`schema.category` → INSERT 哪張表 | |

**方案 B 做不到的情境**：

假設 Line1 的 Printer 是生產線設備（資料放 `ts_telemetry`），  
Line2 的 Printer 是品管站（同樣的 `{temperature, pressure}` 要放 `ts_measurements`）。

```
Line1/Printer/Telemetry → schema_type = "PrinterSensors" (category = telemetry) ✅
Line2/QC_Station/Check  → schema_type = "PrinterSensors" (category = telemetry) ❌ 想要 measurement！
```

方案 B 下，你必須**複製一份幾乎一模一樣的 Schema Type**（只改 `category`）才能解決。

---

### 2.3 方案 C：Namespace Node 加 `data_category` 欄位

在 `namespace_nodes` 表新增 `data_category VARCHAR`。  
Category 綁在**每個 Topic Node** 上，與 Schema Type 解耦。

**機制**：

```yaml
# Schema Type 定義（不含 category！）
Schema Type: "PrinterSensors"
  fields:
    - {name: "temperature", type: "float", deadband: 0.5}
    - {name: "pressure",    type: "float", deadband: 0.05}
  # 沒有 category 欄位
```

Category 在每個 Namespace Node 上各自設定：

```
Line1/Printer/Telemetry
  → schema_type = "PrinterSensors"
  → data_category = "telemetry"     ← 🔑 寫在 Node 上

Line1/Printer/Status
  → schema_type = "PrinterStatus"
  → data_category = "status"        ← 🔑 寫在 Node 上

Line2/QC_Station/Measurement
  → schema_type = "PrinterSensors"  ← 同一個 Schema！
  → data_category = "measurement"   ← 🔑 但路由到不同的表！✅
```

**結果**：Category 和 Topic Node 是 1:1 綁定，和 Schema Type 完全解耦。

| 優點 | 缺點 |
|---|---|
| 最大彈性：同 Schema 可在不同 Node 路由到不同表 | 設定點分散：每個 Node 都要設，100 台 = 設 100 次 |
| 符合現實：同一種感測器裝不同位置，語義不同 | 一致性風險：同 Schema 下不同 Node 可能被設成不同 category |
| UI 更直覺：管理者在 Node 上直接設定資料類型 | Data Engine 路由邏輯稍複雜（需從 Node 帶 category） |

---

## 3. 決策

**採用方案 B 為主、方案 A 做 fallback。為未來方案 C 保留演化空間。**

### 3.1 路由邏輯（優先順序）

```
1. schema_types.category（如果有設定） → 決定目標表
2. Topic 最末段名稱 fallback（如果 category 為 NULL）
3. 預設 → "telemetry"
```

### 3.2 決策理由

1. **PoC 階段簡單為王**：方案 B 的 Data Engine 改動最小，路由邏輯直覺
2. **產業實務**：製藥 CDMO / F&B 工廠中，同一種 Schema Type 通常語義固定（`SMT_Printer_Alarm` 就是 Alarm，不會拿去當 Telemetry 用），方案 B 的限制在這些場景中幾乎不存在
3. **避免過度設計**：方案 C 引入太多設定自由度，增加 UI 複雜度和管理者的認知負擔

---

## 4. 為方案 C 保留彈性的設計原則

> [!IMPORTANT]
> 以下原則是刻意的架構預留，所有實作者務必遵守。

### 原則 1：路由邏輯必須抽象化

Data Engine 中的路由判斷邏輯應封裝為獨立的 `CategoryRouter` 類別（或函式），而非散佈在 Pipeline 各處。

```python
# ✅ 正確做法：封裝路由邏輯
class CategoryRouter:
    def resolve(self, schema_match: SchemaMatch) -> str:
        """決定 category，未來可在此注入 Node 級別覆蓋"""
        if schema_match.category:
            return schema_match.category
        # fallback: 從 topic 最末段推斷
        last_segment = schema_match.topic.split("/")[-1].lower()
        if last_segment in ("telemetry", "status", "alarm", "event", "measurement"):
            return last_segment
        return "telemetry"

# ❌ 錯誤做法：在 Pipeline 中散落路由邏輯
if schema.category == "telemetry":
    writer.write_telemetry(...)
elif topic.endswith("Status"):
    writer.write_status(...)
```

### 原則 2：SchemaMatch 結構體統一提供 `category`

不管 category 來源是 Schema 還是 Node，Pipeline 下游永遠只看 `SchemaMatch.category`，不直接查來源。

```python
@dataclass
class SchemaMatch:
    topic: str
    schema_id: int
    category: str           # ← 統一出口，下游不關心來源
    persist_mode: str
    fields: list[FieldDef]
    ...
```

### 原則 3：DBWriter 使用 Strategy Pattern

每個目標表對應一個 Writer Strategy，新增表只需新增 Strategy，不改核心邏輯。

```python
# 未來架構示意
class DBWriter:
    _strategies = {
        "telemetry":   TelemetryWriterStrategy(),
        "status":      StatusWriterStrategy(),
        "alarm":       AlarmWriterStrategy(),
        "event":       EventWriterStrategy(),
        "measurement": MeasurementWriterStrategy(),
    }

    def write(self, category: str, records: list):
        strategy = self._strategies.get(category)
        if strategy:
            strategy.insert(records)
```

### 原則 4：不在 `namespace_nodes` 上現在就加 `data_category`

避免兩個來源造成混淆。等未來確實需要 Node 級別覆蓋時，再加 `category_override` 欄位：

```sql
-- Phase 3 才加，現在不加
ALTER TABLE namespace_nodes ADD COLUMN category_override VARCHAR;
```

屆時路由優先順序變為：
```
node.category_override > schema.category > topic fallback > "telemetry"
```

---

## 5. Auto-detect 與 Category 的關係

Schema Auto-detect Engine（Feature 6）在偵測到新 Topic 的 Payload 時，除了推斷欄位結構，也需要**建議 category**。

### 5.1 啟發式推斷規則

| 判斷依據 | 建議 category | 說明 |
|---|---|---|
| Topic 路徑包含 `Alarm` | `alarm` | 命名慣例 |
| Payload 含 `severity`, `alarm_code` | `alarm` | 欄位特徵 |
| Payload 含 `state`, `previous_state` | `status` | 狀態機模式 |
| Topic 路徑包含 `Event` | `event` | 命名慣例 |
| Payload 含 `lot_id`, `event_code` | `event` | 事件模式 |
| Topic 路徑包含 `Measurement` / `QC` | `measurement` | 品管情境 |
| 純數值 key-value | `telemetry` | 最常見的預設 |
| 不確定 | `telemetry` | 保守預設，等管理者確認 |

### 5.2 Auto-detect 流程中的 category 處理

```
1. 收到未知 Topic 的 Payload
2. 推斷 fields 結構 + 推斷 category
3. 建立 "suggested" Schema Type（status = "suggested", category = 推斷值）
4. 在 UI 上顯示建議，管理者可修改 category
5. 管理者確認 → status = "confirmed" → 開始 extract + 路由
```

---

## 6. 未來演化路徑

```
Phase 1 (PoC, 現在)
  → schema_types 加 category 欄位
  → CategoryRouter 封裝路由邏輯
  → 僅實作 ts_telemetry + ts_raw_payloads 的寫入
  → 其他 category 暫時 fallback 到 ts_telemetry

Phase 2
  → 開始實作 ts_status, ts_alarms, ts_events, ts_measurements 目標表
  → DBWriter 加入 Strategy Pattern，各表獨立 Writer
  → Auto-detect 加入 category 推斷

Phase 3 (如果需要)
  → namespace_nodes 加 category_override 欄位
  → 路由優先順序：node override > schema category > topic fallback
  → UI 支援在 Node 上覆蓋 category
```

---

## 7. 相關文件

- [platform_system_spec.md](file:///Users/kaihsiang/Documents/Git_Repository/uns-platform/docs/platform_system_spec.md) §3.1 (Namespace Tree), §5 (Schema Type), §6 (Persistence)
- [PROGRESS.md](file:///Users/kaihsiang/Documents/Git_Repository/uns-platform/PROGRESS.md) — Agent Collaboration Contract
- [data-engine/src/pipeline.py](file:///Users/kaihsiang/Documents/Git_Repository/uns-platform/data-engine/src/pipeline.py) — Pipeline 路由主邏輯
- [data-engine/src/db_writer.py](file:///Users/kaihsiang/Documents/Git_Repository/uns-platform/data-engine/src/db_writer.py) — DB 寫入邏輯
- [data-engine/src/schema_matcher.py](file:///Users/kaihsiang/Documents/Git_Repository/uns-platform/data-engine/src/schema_matcher.py) — SchemaMatch 結構體
