# UNS Namespace Data Platform — 系統規格書

> **文件性質**：系統設計概念、資料模型規格、Edge Cases、設計決策紀錄
> **文件版本**：v0.1 (Draft)
> **最後更新**：2026-03-02

---

## 目錄

1. [產品定位與邊界](#1-產品定位與邊界)
2. [系統架構](#2-系統架構)
3. [Namespace 資料模型](#3-namespace-資料模型)
4. [Payload 處理規格](#4-payload-處理規格)
5. [Schema Type 系統](#5-schema-type-系統)
6. [資料持久化規格](#6-資料持久化規格)
7. [Tag 身份管理與 Live Migration](#7-tag-身份管理與-live-migration)
8. [資料存取介面](#8-資料存取介面)
9. [ACL 與安全模型](#9-acl-與安全模型)
10. [Edge Cases 與設計決策](#10-edge-cases-與設計決策)
11. [競品分析與差異化定位](#11-競品分析與差異化定位)
12. [Command Flow（命令流程與 UNS 角色）](#12-command-flow命令流程與-uns-角色)
13. [Event Topic 設計規範](#13-event-topic-設計規範)
14. [AI/LLM 策略與定位](#14-aillm-策略與定位)
15. [MCP Server 設計](#15-mcp-server-設計)
16. [術語表](#16-術語表)

---

## 1. 產品定位與邊界

### 1.1 定位

| | 本產品 | HighByte | EMQX | UMH | Ignition |
|---|---|---|---|---|---|
| 角色 | UNS 資料平台 | DataOps 中間件 | MQTT Broker | 開源 IIoT | SCADA |
| 存資料 | ✅ | ❌ | ❌ | ✅ | ✅ |
| Namespace 管理 | ✅ | ✅ v4.0 | ❌ | ❌ | 弱 |
| Tag 身份分離 | ✅ | ❌ | ❌ | ❌ | ❌ |
| Live Migration | ✅ | ❌ | ❌ | ❌ | ❌ |

### 1.2 本產品是什麼

- 工廠 UNS 的中央管理平台
- 結合 Namespace 管理 + MQTT Broker + Time-Series Historian
- 資料收進來之後就住在這裡，成為工廠資料的 Single Source of Truth
- 所有周邊系統（MES / ERP / SPC / Dashboard）來這裡拿資料

### 1.3 本產品不是什麼

- **不是 MES** — 不管 Lot 狀態、不管 Route 定義
- **不是 SCADA** — 不做 HMI、不做設備控制
- **不是 MQTT Broker** — 用 EMQX / Mosquitto，不自己做
- **不是 IIoT 平台** — 不做 Device Management、不做 OTA
- **不是 ETL 工具** — 不做跨系統資料搬運（HighByte 的領域）

### 1.4 目標市場選擇原則

```
好的產品 ≠ 好的生意
好的生意 = 好的產品 × 深刻的產業理解 × 信任關係

市場選擇的第一優先順序不是「市場規模最大」，
而是「我們最有 domain knowledge 的產業」。
沒有 domain knowledge，即使技術適用也打不進去。
```

### 1.5 產業自動化成熟度光譜

```
  紙本作業 ◄──────────────────────────────────► 全自動 CIM

     │   F&B 中小型        Pharma 大型          │
     │   ├── 53-65% OEE    ├── 有 MES           │  半導體
     │   ├── 手動記錄       ├── 有 EBR           │  ├── CIM + EAP
     │   ├── Excel 報表     ├── 正在上 IoT       │  ├── 成熟方案
     │   └── 沒有 MES       └── DCS/SCADA        │  └── 不會採用 UNS
     │                                           │
   Level 1         我們的甜蜜點 →              Level 5

  ❌ Level 5（半導體）：已有成熟方案，不會用 UNS
  ❌ Level 1（純手工）：連 PLC 都沒有，UNS 無用武之地
  ✅ Level 2-3（有設備、有基本 SCADA、正在或想要導入 MES）：最需要 UNS
```

### 1.6 主要目標市場

#### 🥇 首選：製藥 CDMO + 精密化學

| 指標 | 製藥 | 精密化學 |
|---|---|---|
| MES 市場 | $27.7 億→$60 億 (CAGR 11.7%) | 隨製藥成長 |
| EBR 市場 | $7 億→$25 億 (CAGR 15.2%) | — |
| 驅動力 | FDA 21 CFR Part 11 合規壓力 | 製程最佳化 + 追溯 |
| 現狀 | 很多仍紙本，正大量導 MES | DCS/SCADA 為主 |
| UNS 賣點 | 批次追溯 + Audit + 製程-品質關聯 | 批次參數追蹤 + SPC |
| 理想客戶 | 中型 CDMO（$1-10 億營收） | 中型化學品廠 |

```
為什麼是首選：
  ✅ Domain Knowledge — Yokogawa 核心客戶群，我們懂他們的 operation
  ✅ 法規驅動 — 不是「想不想」數位轉型，是「不得不」
  ✅ 願意付錢 — 藥廠利潤高、合規成本高
  ✅ 批次製程 — Production Context 有直接價值
  ✅ 很多還在紙本 — UNS 入門門檻低（不用取代既有系統）
```

#### 🥈 次選：食品飲料 F&B + 電子代工 EMS/SMT

| 指標 | F&B | EMS/SMT |
|---|---|---|
| 驅動力 | OEE 低（53-65%）、多產線 | 多設備、品質追溯 |
| 現狀 | 93% 正在數位轉型 | 設備有通訊能力 |
| UNS 賣點 | OEE 即時看板 + 設備狀態 | SPC + 品質追溯 |
| 理想客戶 | 中型 F&B（多條線） | 中型 EMS（500-5000 人）|
| 注意 | 預算 cost-driven、客單價低 | 大廠已有自建系統 |

#### ❌ 明確排除

| 產業 | 排除理由 |
|---|---|
| 半導體 / 光電 | 已有成熟 CIM 方案，不可能採用 UNS |
| 汽車 OEM | Siemens / Rockwell 主戰場，競爭太激烈 |
| 水務 / 公用事業 | 我們無 domain knowledge，無法與傳統 SCADA 廠商競爭 |

### 1.7 分層產品策略

針對不同自動化成熟度的客戶：

| 客戶成熟度 | 有什麼 | 缺什麼 | UNS 賣什麼 |
|---|---|---|---|
| **Level 1** (PLC only) | PLC 控制設備 | 沒有即時數據 | Tier 1：設備資料收集 + 看板 |
| **Level 2** (PLC+SCADA) | 有即時數據 | 沒有 Historian、沒有 OEE | Tier 2：Historian + OEE + 設備狀態 |
| **Level 3** (有 MES) | MES 管批次 | 資料孤島、沒有 SPC | Tier 3：Production Context + SPC |

```
核心策略：
  不要求客戶一次到位（全自動整合）。
  在 Tier 1 就能提供價值（設備資料 + 看板）。
  隨客戶成熟度提升，逐步 upsell Tier 2 → Tier 3。

  Production Context 不一定要靠 MES 的 CDC：
  ✅ 有 MES → CDC 自動同步
  ✅ 沒有 MES → 操作員在 UI 上手動輸入 Lot 資訊
     「Line1/Mixer → Start Run → Lot: LOT-001」
     → 一個人、一個按鈕、就把 Production Context 建起來
```

---

## 2. 系統架構

### 2.1 元件清單

```
┌──────────────────────────────────────────────────────┐
│                UNS Data Platform                     │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  Namespace Manager (Web UI)                  │    │
│  │  前端：React                                  │    │
│  │  功能：Namespace Tree Editor / Tag CRUD /     │    │
│  │        Schema Type 管理 / ACL 設定 /          │    │
│  │        Per-topic Persistence Config          │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  Platform Backend (FastAPI)                  │    │
│  │  - Namespace CRUD API                        │    │
│  │  - Tag Registry API                          │    │
│  │  - Schema Type API                           │    │
│  │  - ACL Management → EMQX REST API sync       │    │
│  │  - Migration Engine                          │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  Data Engine                                 │    │
│  │  - MQTT Consumer（訂閱所有 topic）             │    │
│  │  - Payload Decoder（JSON / Sparkplug / Text） │    │
│  │  - Schema Matcher（payload → Schema Type）    │    │
│  │  - Field Extractor（JSONPath → Tag values）   │    │
│  │  - DB Writer（batch INSERT to TimescaleDB）   │    │
│  │  - Auto-detect Engine（自動偵測 payload 結構） │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                │
│  ┌──────────────────▼───────────────────────────┐    │
│  │  EMQX (外部元件，不自己開發)                    │    │
│  │  - MQTT Broker                               │    │
│  │  - ACL enforcement                           │    │
│  │  - Retained messages                         │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  TimescaleDB (外部元件)                       │    │
│  │  - Namespace 定義（namespace_nodes）           │    │
│  │  - Tag Registry（tags + tag_source_mapping）  │    │
│  │  - Schema Types（schema_types）               │    │
│  │  - Time-Series（ts_telemetry, ts_status...）  │    │
│  │  - Raw Payloads（ts_raw_payloads）            │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### 2.2 部署模型

Phase 1 目標：單一 Docker Compose 啟動所有元件。

```
docker compose up
  → EMQX (port 1883/8883)
  → TimescaleDB (port 5432)
  → Platform Backend (port 8000)
  → Namespace Manager UI (port 3000)
  → Data Engine (background)
```

---

## 3. Namespace 資料模型

### 3.1 Namespace Tree 結構

Namespace 是一棵樹，遵循 ISA-95 階層：

```
Enterprise
  └── Site
        └── Area
              └── Line
                    └── Equipment
                          ├── [Topic] Telemetry  ← 綁定 Schema Type
                          ├── [Topic] Status
                          ├── [Topic] Alarm
                          └── [Topic] Measurement
```

Node 分兩種：
- **Structural Node**：純階層用（Enterprise / Site / Area / Line / Equipment）
- **Topic Node**：對應到一個 MQTT topic，可以收發資料

### 3.2 Namespace Node 表

```sql
CREATE TABLE namespace_nodes (
    node_id         SERIAL PRIMARY KEY,
    parent_id       INTEGER REFERENCES namespace_nodes(node_id),
    name            TEXT NOT NULL,           -- "Line1", "Printer", "Telemetry"
    node_type       TEXT NOT NULL,           -- structural / topic
    full_path       TEXT NOT NULL UNIQUE,    -- "Enterprise/Site/Area/Line1/Printer/Telemetry"

    -- Topic Node 專屬
    schema_type_id  INTEGER REFERENCES schema_types(type_id),
    persist_mode    TEXT DEFAULT 'db',       -- db / retain / passthrough
    retention_days  INTEGER DEFAULT 90,

    -- Metadata
    description     TEXT,
    icon            TEXT,                    -- UI 顯示用
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ              -- Soft delete
);
```

### 3.3 full_path 就是 MQTT topic

```
Namespace node full_path = MQTT topic path
  namespace_nodes.full_path = "TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry"
  MQTT topic               = "TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry"

這兩者必須一致。Namespace Manager 是 topic 的「權威來源」。
```

---

## 4. Payload 處理規格

### 4.1 三種 Payload 複雜度

| Level | 結構 | 範例 | 處理方式 |
|---|---|---|---|
| **L1 Simple** | 單一 key-value | `{"value": 25.3}` | 直接取值 |
| **L2 Flat** | 扁平多參數 | `{"temp": 25, "pressure": 2.1}` | 取每個 key |
| **L3 Complex** | 巢狀 / 陣列 | `{"zones": [{...}]}` | JSONPath extract |

### 4.2 Payload 解碼器（Decoder）

進入 Data Engine 的第一步是解碼：

| Decoder | 適用場景 | 輸出 |
|---|---|---|
| `json` | 標準 JSON payload（預設） | Python dict |
| `sparkplug` | Sparkplug B (Protobuf) | Python dict |
| `text_float` | 純文字數值 `"25.3"` | `{"value": 25.3}` |
| `text_csv` | CSV 格式 `"25.3,2.1,50"` | 依 schema 定義對應欄位 |
| `custom` | 使用者自訂（Phase 2+） | Script 輸出 |

Phase 1 只實作 `json`，架構上預留擴展點。

### 4.3 Payload 處理流程

```
MQTT Message 進來
    │
    ▼
[1] Decoder（解碼 → dict）
    │
    ▼
[2] Schema Matcher（找到對應的 Schema Type）
    │  ├── 有 Schema Type → 用定義好的 extract rules
    │  └── 沒有 → auto-detect 模式（建議 schema）
    │
    ▼
[3] Field Extractor（依 Schema Type 拆解欄位）
    │  └── 每個欄位 → (tag_id, value, timestamp)
    │
    ▼
[4] Persist Decision（依 persist_mode 決定）
    │  ├── db → batch INSERT to ts_telemetry
    │  ├── retain → 只更新 MQTT retained（不寫 DB）
    │  └── passthrough → 不處理
    │
    ▼
[5] Raw Storage（如果 Schema Type 設定 store_raw = true）
    │  └── INSERT to ts_raw_payloads
    │
    ▼
[6] Metrics Update（更新 Consumer metrics）
```

---

## 5. Schema Type 系統

### 5.1 概念

Schema Type 是可重用的 payload 結構定義，類似 OOP 的 class。

```
Schema Type: "SMT_Printer_Telemetry"（定義一次）
  → 套用到 Line1/Printer/Telemetry（實例 1）
  → 套用到 Line2/Printer/Telemetry（實例 2）
  → 套用到 Line3/Printer/Telemetry（實例 3）

100 台同型設備 → 同一個 Schema Type
```

### 5.2 Schema Type 完整定義

```yaml
type_name: "SMT_Printer_Telemetry"
decoder: "json"
timestamp_field: "_meta.timestamp"         # payload 中的時間戳欄位（null = 用 MQTT 收到時間）
store_raw: true
raw_retention_days: 30

# 欄位未定義的 payload 如何處理
on_schema_mismatch: "log_and_store"        # strict / log_and_store / reject
on_new_field: "suggest"                    # auto_create / suggest / ignore

fields:
  - name: "temperature"                    # Tag 名稱
    path: "$.temperature"                  # JSONPath（L1/L2 可省略，直接用 key）
    type: "float"                          # float / integer / string / boolean / json
    unit: "°C"
    extract: true                          # 是否拆解為獨立 Tag
    persist: true                          # 是否寫入 ts_telemetry
    deadband: 0.1                          # 變化量 < 此值不寫入（null = 全部寫）
    array_mode: "single"                   # single / expand / avg / last

  - name: "pressure"
    path: "$.pressure"
    type: "float"
    unit: "kPa"
    extract: true
    persist: true
    deadband: 0.05

  - name: "recipe_name"
    path: "$.recipe_name"
    type: "string"
    extract: true
    persist: true
    deadband: "change_only"                # 值沒變就不寫

  - name: "humidity"
    path: "$.humidity"
    type: "float"
    unit: "%"
    extract: true
    persist: false                         # 不存 DB，只 retain
```

### 5.3 欄位型別定義

| type | 儲存在 ts_telemetry 的方式 | 說明 |
|---|---|---|
| `float` | `value` (DOUBLE PRECISION) | 數值，SPC / OEE 的核心 |
| `integer` | `value` (DOUBLE PRECISION) | 整數，存為 float |
| `string` | `value_text` (TEXT) | 字串，如 recipe_name / state |
| `boolean` | `value` (1.0 / 0.0) | 布林轉數值 |
| `json` | `value_json` (JSONB) | 複雜物件，不拆解直接存 |

### 5.4 array_mode 定義

當 JSONPath 取出的值是陣列時（如 `$.zones[*].temp`）：

| mode | 行為 | 適用場景 |
|---|---|---|
| `single` | 取第一個值 | 通常是錯誤配置 |
| `expand` | 拆成 N 筆，各自獨立 timestamp | EAP batch trace data |
| `avg` | 取平均值存一筆 | 統計摘要 |
| `last` | 取最後一個值 | 最新狀態 |

### 5.5 deadband 定義

| 設定 | 行為 |
|---|---|
| `null`（不設定） | 每筆都寫入 |
| `0.1`（數值） | 和上一筆的差異 < 0.1 → 跳過 |
| `"change_only"` | 值完全沒變 → 跳過（適合字串） |

Deadband 狀態由 Data Engine 在記憶體中維護：
`{tag_id: last_persisted_value}`

### 5.6 Schema Type DB 表

```sql
CREATE TABLE schema_types (
    type_id            SERIAL PRIMARY KEY,
    type_name          TEXT NOT NULL UNIQUE,
    decoder            TEXT DEFAULT 'json',
    timestamp_field    TEXT,
    store_raw          BOOLEAN DEFAULT true,
    raw_retention_days INTEGER DEFAULT 30,
    on_schema_mismatch TEXT DEFAULT 'log_and_store',
    on_new_field       TEXT DEFAULT 'suggest',
    fields             JSONB NOT NULL,          -- 欄位定義陣列
    version            INTEGER DEFAULT 1,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.7 Auto-detect 引擎

```
輸入：收到一筆 payload，但該 topic 沒有綁定 Schema Type
處理：
  1. Parse payload → 取得所有 key + value
  2. 推斷每個 key 的 type（float / string / boolean / json）
  3. 如果是第一次看到這個 topic → 建立 "suggested" Schema Type
  4. 如果已有 suggested → 比對新 payload 和既有定義
     - 新欄位 → 標記為 "detected_new_field"
     - 欄位消失 → 標記為 "optional"
     - 型別改變 → 標記為 "type_conflict"
  5. 在 UI 上顯示建議，等管理者確認

狀態：
  suggested → 尚未確認，資料只存 raw
  confirmed → 管理者確認，開始 extract + persist
  modified  → 管理者調整過

Auto-detect 累積 N 筆（預設 100）payload 後才產生建議，
避免單一異常 payload 產生錯誤推斷。
```

---

## 6. 資料持久化規格

### 6.1 Per-Topic Persistence Mode

| Mode | 寫 DB | MQTT Retain | 適用場景 |
|---|---|---|---|
| `db` | ✅ | ✅ | 溫度、壓力等需要歷史分析的資料 |
| `retain` | ❌ | ✅ | 設備狀態、最新值快取 |
| `passthrough` | ❌ | ❌ | 純 event / command / heartbeat |

Persist mode 設定在 `namespace_nodes` 表的 topic node 上。

### 6.2 Dual Storage

```
所有 persist_mode = "db" 的資料同時做兩件事：

  1. Raw Storage（ts_raw_payloads）
     - 整包 MQTT payload 原封不動存
     - retention 短（預設 30 天）
     - 用途：backfill、除錯、schema 修正後重新 extract

  2. Extracted Storage（ts_telemetry / ts_status / ...）
     - 拆解後的個別 Tag 值
     - retention 長（預設 90 天，可自訂）
     - 用途：SPC / OEE / Dashboard / API 查詢
```

### 6.3 Dual Storage 的取捨

| | 優點 | 缺點 |
|---|---|---|
| 只存 raw | 最彈性，事後可重新 parse | 查詢需 runtime parse JSON，慢 |
| 只存 extracted | 查詢快，直接用 index | Schema 定義錯了就丟資料 |
| **Dual（預設）** | 兩者兼得，Schema 錯了可補救 | 2x 儲存成本 |

**設計決策**：預設 Dual Storage。raw 保留期短，確認 extract 正確後自然過期。
管理者亦可關閉 raw storage（`store_raw: false`）以節省空間。

### 6.4 Backfill 功能

```
情境：Schema Type 修改了 extract rule（加新欄位、修正 JSONPath）。
     過去的 raw payload 需要重新 extract。

流程：
  1. 管理者在 UI 點「Backfill」
  2. 系統掃描 ts_raw_payloads 中對應 topic 的歷史 payload
  3. 用新的 Schema Type 重新 extract
  4. INSERT 到 ts_telemetry（跳過已存在的 time + tag_id 組合）
  5. 顯示 backfill 結果：成功 N 筆、失敗 N 筆、新 Tag N 個
```

---

## 7. Tag 身份管理與 Live Migration

### 7.1 核心原則

```
tag_id 是永久不變的 identifier（學 OSIsoft PI 的設計）。
MQTT topic 改了 → tag_source_mapping 更新 → tag_id 不變 → 歷史資料連續。
```

### 7.2 涉及的表

| 表 | 角色 |
|---|---|
| `tags` | Tag 的永久身份（tag_id, display_name, unit, data_type） |
| `tag_source_mapping` | MQTT topic → tag_id 的對應（可多對一） |
| `namespace_nodes` | Namespace 階層結構（UI 上看到的樹） |

### 7.3 Live Migration 場景

**場景：管理者把 Line1/Printer 拖到 Line2/Printer**

```
Before:
  namespace_nodes: /Enterprise/Site/SMT/Line1/Printer/Telemetry
  tag_source_mapping:
    mqtt_topic = "Enterprise/Site/SMT/Line1/Printer/Telemetry" → tag_id = 42
  tags:
    tag_id = 42, asset_path = "Enterprise/Site/SMT/Line1/Printer"

After:
  namespace_nodes: /Enterprise/Site/SMT/Line2/Printer/Telemetry  ← path 改了
  tag_source_mapping:
    mqtt_topic = "Enterprise/Site/SMT/Line1/Printer/Telemetry" → deactivated
    mqtt_topic = "Enterprise/Site/SMT/Line2/Printer/Telemetry" → tag_id = 42  ← 新 mapping
  tags:
    tag_id = 42, asset_path = "Enterprise/Site/SMT/Line2/Printer"  ← 更新顯示路徑

  ts_telemetry:
    完全不動。tag_id = 42 的歷史資料自動包含搬遷前後的所有值。
```

### 7.4 Migration 涉及的額外動作

| 動作 | 說明 |
|---|---|
| 更新 EMQX ACL | 舊 topic 的 ACL 失效，新 topic 的 ACL 生效 |
| 通知 connected devices | 可透過 MQTT system topic 或 REST API 告知設備更新 topic |
| Audit Log | 記錄誰、什麼時候、做了什麼變更 |
| 下游 Consumer 通知 | 訂閱舊 topic 的 Consumer 需要更新訂閱 |

### 7.5 不允許的操作

| 操作 | 原因 | 替代方案 |
|---|---|---|
| 直接刪除 Tag | 歷史資料會孤立 | Soft delete（標記 deleted_at） |
| 合併兩個 Tag（不同 tag_id） | 歷史資料型態可能不同 | 建立 virtual tag（view） |
| 改變 Tag 的 data_type | 歷史資料的型別已固定 | 建立新 Tag，舊 Tag deactivate |

---

## 8. 資料存取介面

### 8.1 資料流完整矩陣

**寫入方向（資料進入 UNS）：**

| 寫入方式 | 適合誰 | 協議 | 發佈到 MQTT Topic? | 存 DB? |
|---|---|---|---|---|
| **MQTT publish** | L0-L2 設備 | MQTT | ✅ 原生 | 依 persist config |
| **REST POST** | 外部系統 / 手動 | HTTP | ✅ 轉發到 topic | 依 persist config |
| **gRPC Write** | L3-L4 系統（MES/ERP） | gRPC | ✅ 轉發到 topic | ✅ |
| **CDC** | MES/ERP DB 變更 | Debezium | ✅ 轉發到 topic | ✅ |

**讀取方向（資料從 UNS 出去）：**

| 讀取方式 | 適合誰 | 協議 | 資料類型 |
|---|---|---|---|
| **MQTT subscribe** | 即時 Consumer / Dashboard | MQTT | Real-time |
| **gRPC Query** | SPC / EDA / 分析系統 | gRPC | 歷史 + 即時 |
| **REST GET** | Dashboard / 簡單查詢 | HTTP | 歷史 + 即時 |

**核心原則：不管資料從哪裡進來（MQTT / REST / gRPC / CDC），最終都會 publish 到對應的 MQTT topic。**
Namespace Topic Tree 是唯一的資料流動通道，所有即時 Consumer 都能收到。

### 8.2 L3/L4 系統整合路徑

MES / ERP 等 L3-L4 系統有三條路徑把資料送到 UNS：

```
路徑 1（主力）：CDC — MES DB 變更被動同步到 UNS
  適合：大量交易紀錄、持續同步
  延遲：秒級
  機制：Debezium 監聽 MES DB → 轉換為 MQTT payload → publish

路徑 2（補充）：gRPC Write — L3/L4 主動推
  適合：即時 event（LotMoveIn 當下就推）、無法用 CDC 的系統
  延遲：毫秒級
  機制：MES 呼叫 gRPC WriteEvent() → 寫入 DB + publish 到 MQTT topic

路徑 3（輕量）：REST POST — 簡單整合
  適合：沒有 gRPC SDK 的系統、手動操作、CSV import
  延遲：毫秒級
  機制：POST /api/v1/data/{topic} → 進入 Data Engine pipeline
```

### 8.3 L3/L4 寫入的資料分兩類

| 類型 | 說明 | 走 Namespace Topic? | 儲存位置 |
|---|---|---|---|
| **Event Data** | LotMoveIn/Out, QualityHold, RecipeDownload 等 | ✅ publish 到 `.../Event/{category}` | `ts_events` |
| **Master Data** | Recipe 定義、Product 定義、Work Order | ❌ 不是時序資料 | 獨立 reference table |

Master Data 寫入時，同時 publish 一個 "change notification" 到 MQTT topic，
讓訂閱者知道有更新，但不存時序。

### 8.4 REST API

```
寫入（外部 → UNS）：
POST /api/v1/data/{topic_path}
Content-Type: application/json

{
  "timestamp": "2024-01-15T08:30:00+08:00",
  "payload": {
    "temperature": 25.3,
    "pressure": 2.1
  }
}

→ 進入和 MQTT 相同的 Data Engine pipeline
→ Decode → Schema Match → Extract → Persist
→ 同時 publish 到對應的 MQTT topic

查詢（UNS → 外部）：
GET /api/v1/tags/{asset_path}/values?from=...&to=...
GET /api/v1/namespace/tree
GET /api/v1/tags/{asset_path}/latest
```

### 8.5 gRPC API

```protobuf
service UNSDataService {
  // ── 查詢（Read）──
  rpc BrowseNamespace(BrowseRequest) returns (NamespaceTree);
  rpc ListTags(ListTagsRequest) returns (TagList);
  rpc QueryTimeSeries(TimeSeriesRequest) returns (stream TimeSeriesData);
  rpc QueryMeasurements(MeasurementRequest) returns (MeasurementData);
  rpc GetLatestValues(LatestValuesRequest) returns (LatestValues);

  // ── L3/L4 Event 寫入（Write）──
  rpc WriteEvent(EventRequest) returns (WriteResponse);
  rpc WriteEventStream(stream EventRequest) returns (WriteResponse);  // 批次

  // ── L3/L4 Master Data（Read/Write）──
  rpc GetProductionRun(RunQuery) returns (ProductionRun);
  rpc UpdateProductionRun(RunUpdate) returns (WriteResponse);
}

// WriteEvent 進來後的處理流程：
//   1. 寫入 ts_events
//   2. 同時 publish 到對應的 MQTT topic（讓即時 Consumer 收到）
//   3. 如果是 LotMoveIn/Out → 同步更新 production_run
```

---

## 9. ACL 與安全模型

### 9.1 分層存取控制

```
Layer 1: MQTT Broker（EMQX）
  → 設備認證（username/password 或 X.509 cert）
  → Topic ACL（誰可以 pub/sub 哪些 topic）
  → 由 Namespace Manager 自動同步到 EMQX

Layer 2: Platform API（FastAPI / gRPC）
  → JWT 或 API Key 認證
  → RBAC 角色：admin / engineer / operator / readonly

Layer 3: Database（TimescaleDB）
  → PostgreSQL 角色分離（uns_admin / uns_writer / uns_reader）
```

### 9.2 ACL 設定模型

```
在 Namespace node 上設定 ACL：
  node: /Enterprise/Site/Line1/Printer
  acl:
    - principal: "printer-line1"    # MQTT username
      permission: publish           # publish / subscribe / both
      inherit: true                 # 子 node 繼承

ACL 繼承：子 node 自動繼承父 node 的 ACL，可 override。
```

### 9.3 EMQX ACL 同步

```
Namespace Manager ACL 變更
    │
    ▼
Platform Backend 呼叫 EMQX REST API
    │
    ├── PUT /api/v5/authorization/sources/built_in_database/rules/users/{username}
    │   → 更新該 user 的 topic ACL
    │
    └── 或 生成 ACL 檔案 → EMQX 重載
```

---

## 10. Edge Cases 與設計決策

### EC-1：批次 payload（一筆訊息帶多個時間點）

```
場景：EAP 加工完後上傳 300 筆 trace data。
設計決策：
  - Schema Type field 的 array_mode = "expand"
  - Data Engine 展開為 N 筆 ts_telemetry
  - 每筆的 timestamp 根據 start_time + index × interval_ms 計算
  - 用 batch INSERT (execute_values) 寫入
  - 同 §17 Production Context 的 commanded mode 設計
```

### EC-2：Schema Evolution（payload 結構變更）

```
場景：設備韌體更新，payload 多了新欄位。
設計決策：
  - on_new_field = "suggest" → UI 顯示 ⚠️ 建議確認
  - on_new_field = "auto_create" → 自動建 Tag（小規模時可用）
  - on_new_field = "ignore" → 丟棄未定義的欄位

  - 新欄位的資料在確認前存在 raw payload 中不會遺失
  - 確認後可 backfill
```

### EC-3：同一 topic 不同 schema

```
場景：兩種設備型號 publish 到同一個 topic 但 payload 結構不同。
設計決策：
  - Phase 1：不允許。一個 topic node 只能綁一個 Schema Type。
    → 設備必須 pub 到不同 topic。
  - Phase 2：支援 discriminator field（用 payload 的某個欄位區分）。
    → discriminator: "_meta.device_model"
    → "ModelA" → Schema Type A
    → "ModelB" → Schema Type B
```

### EC-4：非 JSON payload

```
場景：Sparkplug B (Protobuf)、純文字、Binary。
設計決策：
  - Phase 1 只支援 JSON。
  - 架構上預留 decoder 擴展點。
  - Sparkplug B 是 Phase 2 優先項（因為 Ignition 生態龐大）。
```

### EC-5：Timestamp 衝突

```
場景：payload.timestamp 和 MQTT receive time 不同。
設計決策：
  - 優先用 payload 中的 timestamp（由 Schema Type 的 timestamp_field 指定）
  - 如果 payload 沒有 timestamp → 用 MQTT receive time
  - 如果 payload timestamp 和 receive time 差 > 5 分鐘 → 記 warning
    （可能是設備時鐘不準或網路延遲）
```

### EC-6：高頻 vs 低頻資料混在同一 topic

```
場景：一個 payload 同時包含每秒變動的溫度和一天變一次的 recipe_name。
設計決策：
  - 每個 field 獨立的 deadband 設定
  - temperature: deadband = 0.1（變化 < 0.1°C 不存）
  - recipe_name: deadband = "change_only"（值沒變就不存）
  - Deadband 狀態在 Data Engine 記憶體中維護
```

### EC-7：超大 payload

```
場景：AOI 影像（>1MB）透過 MQTT 傳送。
設計決策：
  - 定義 payload size limit（預設 1MB，可設定）
  - 超過 limit 時：
    - 選項 A：拒絕，回傳 MQTT PUBACK 錯誤碼
    - 選項 B：存到 Object Storage (MinIO/S3)，DB 存 reference URL
  - Phase 1 用選項 A（直接限制大小）
  - Phase 2 考慮選項 B
```

### EC-8：欄位資料型態不一致

```
場景：同一 field 有時是 integer，有時是 string。
設計決策：
  - Schema Type 定義了 type = "float" → 嘗試 cast
  - Cast 成功 → 正常寫入
  - Cast 失敗 → 存到 raw payload，該 field 標記 type_mismatch
  - UI 顯示 ⚠️ 提醒管理者
```

### EC-9：Retained Message 和 Historian 的衝突

```
場景：Consumer 重啟時收到 retained message，可能造成重複寫入。
設計決策：
  - 冪等寫入：INSERT 前檢查 (tag_id, time) 是否已存在
  - TimescaleDB: ON CONFLICT (tag_id, time) DO NOTHING
  - Consumer 啟動時標記 "bootstrap mode"，retained messages 只更新 cache 不寫 DB
```

### EC-10：Namespace node 刪除

```
場景：管理者刪除一個 Equipment node。
設計決策：
  - Soft delete：標記 deleted_at，不真刪
  - 歷史資料保留，按 retention policy 自然過期
  - tags 和 tag_source_mapping 標記為 inactive
  - EMQX ACL 移除（不再允許 pub/sub）
  - 如果仍有設備 pub 到該 topic → UI 顯示 "orphan data" 警告
  - 可還原（undelete）
```

---

## 11. 競品分析與差異化定位

### 11.1 競品功能矩陣

| 功能 | 本產品 | HighByte | EMQX | UMH | ThingsBoard | Ignition |
|---|---|---|---|---|---|---|
| Namespace 管理 UI | ✅ 拖拉式 | ✅ v4.0 | ❌ | ❌ | ❌ 扁平 | 弱 |
| MQTT Broker | EMQX 整合 | 內建簡易 | ✅ 核心 | MQTT+Kafka | ✅ | Sparkplug |
| Historian | ✅ TimescaleDB | ❌ | ❌ | ✅ TimescaleDB | ✅ Postgres | ✅ |
| Tag 身份分離 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Live Migration | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Per-topic persist | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Schema 管理 | ✅ Schema Type | ❌ | ❌ | ❌ | Device Profile | UDT |
| ACL 管理 | ✅ → EMQX | ❌ | ✅ 內建 | 基本 | ✅ | 基本 |
| Production Context | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SPC / OEE | ✅ | ❌ | ❌ | ❌ | ❌ | Module |
| 價格 | TBD | $17.5K/年 | $2.5~25K/年 | 免費 | 有免費版 | $4~30K+ |

### 11.2 我們的三大差異化

| # | 差異化 | 為什麼重要 | 競品有嗎 |
|---|---|---|---|
| 1 | **Tag 身份分離 + Live Migration** | 工廠設備搬遷頻繁，歷史資料不能斷 | 全部沒有 |
| 2 | **Per-Topic Persistence Config** | 不是所有資料都值得存，精細控制省成本 | 全部沒有 |
| 3 | **Production Context Layer** | IoT 資料沒有 Lot/Step context = 廢物 | 全部沒有 |

### 11.3 半導體 EDA 的教訓

```
傳統 EDA 的資料儲存模式：
  - Wide Table（每 SVID 一個欄位）→ 已淘汰
  - EAV（每個值一筆 row）→ 現在主流，但查詢慢
  - PI System（壓縮 binary）→ 寫入快但查詢需 API

我們的做法：
  - EAV on TimescaleDB（hypertable 自動分 chunk + 壓縮）
  - 兼具 EAV 的彈性和 time-series DB 的查詢效能
  - 加上 Production Context → 不需要 JOIN 外部 MES DB
```

---

## 12. Command Flow（命令流程與 UNS 角色）

### 12.1 核心原則

```
UNS 不是 Command 的通道，是 Command 的紀錄者。

❌ 命令不經過 UNS（MQTT 不保證送達順序、不保證設備有收到）
✅ 命令走直接通道（MES → EAP/PLC：OPC UA / REST / 專用協議）
✅ UNS 旁觀並記錄整個過程的每一個 event
```

### 12.2 時序圖：MES 命令設備加工

以 Pharma 批次製程為例：

```
  MES          UNS (observer)        EAP/PLC         Equipment
   │                │                   │                │
   │ ①LotMoveIn     │                   │                │
   ├───────────────►│ CDC/gRPC          │                │
   │                │ record event      │                │
   │                │                   │                │
   │ ②DownloadRecipe│                   │                │
   ├────────────────┼──────────────────►│                │
   │                │                   │  ③SetRecipe    │
   │                │                   ├───────────────►│
   │                │                   │  ④RecipeAck    │
   │                │                   │◄───────────────┤
   │  ⑤RecipeReady  │                   │                │
   │◄────────────────────────────────────┤                │
   │                │                   │                │
   │                │ ⑥recipe_downloaded│                │
   │                │◄──────────────────┤ event publish  │
   │                │ record event      │                │
   │                │                   │                │
   │ ⑦StartProcess  │                   │                │
   ├────────────────┼──────────────────►│                │
   │                │                   │  ⑧Start        │
   │                │                   ├───────────────►│
   │                │                   │                │
   │                │ ⑨process_started  │                │
   │                │◄──────────────────┤ event publish  │
   │                │ record event      │                │
   │                │                   │                │
   │                │ ⑩ telemetry       │    加工中...    │
   │                │◄──────────────────┼────────────────┤
   │                │ 每秒收溫度/壓力    │  MQTT publish  │
   │                │ persist to DB     │                │
   │                │                   │                │
   │                │                   │  ⑪ProcessEnd   │
   │                │                   │◄───────────────┤
   │                │ ⑫process_completed│                │
   │                │◄──────────────────┤ event publish  │
   │                │ record event      │                │
   │                │                   │                │
   │  ⑬TraceData    │                   │                │
   │                │◄──────────────────┤ batch upload   │
   │                │ persist to DB     │                │
   │                │                   │                │
   │ ⑭LotMoveOut    │                   │                │
   ├───────────────►│ CDC/gRPC          │                │
   │                │ record event      │                │
   │                │ close prod_run    │                │
```

### 12.3 UNS 記錄的 Event

| # | Event | 來源 | 寫入方式 | 存到哪裡 | 用途 |
|---|---|---|---|---|---|
| ① | LotMoveIn | MES | CDC / gRPC | `production_run` (start) | 生產追溯 |
| ⑥ | recipe_downloaded | EAP | MQTT publish | `ts_events` | 稽核 |
| ⑨ | process_started | EAP | MQTT publish | `ts_events` + `production_run` | OEE 計算 |
| ⑩ | telemetry (持續) | Equipment | MQTT publish | `ts_telemetry` | SPC / FDC |
| ⑫ | process_completed | EAP | MQTT publish | `ts_events` + `production_run` | OEE 計算 |
| ⑬ | trace_data (批次) | EAP | MQTT publish | `ts_telemetry` (expand) | EDA |
| ⑭ | LotMoveOut | MES | CDC / gRPC | `production_run` (end) | 生產追溯 |

### 12.4 UNS 不記錄的（不是 UNS 的職責）

| 動作 | 為什麼不記錄 |
|---|---|
| MES → EAP DownloadRecipe | Command channel，不經過 UNS |
| EAP ↔ Equipment 設定 Recipe | 設備協議層（OPC UA / SECS/GEM） |
| EAP → MES RecipeReady 回覆 | MES 的內部 transaction |
| MES → EAP StartProcess | Command channel |
| Equipment → EAP ProcessEnd | 設備協議層（EAP 收到後會 publish event 到 UNS） |

### 12.5 設計決策

```
Q: 為什麼命令不經過 UNS？
A: 三個理由：
   1. MQTT 是 fire-and-forget，不保證設備收到命令
   2. 生產命令需要同步 request/response 確認（OPC UA / gRPC 支援）
   3. UNS 的定位是「資料平台」不是「控制系統」

Q: EAP 怎麼知道要 publish event 到 UNS？
A: EAP 內建 MQTT client，在每個關鍵操作完成後 publish：
   - 設備協議操作完成 → publish event 到 .../Event/Process
   - 不影響原有的 MES ↔ EAP 直接通訊
   - UNS 是「附加的紀錄通道」，不是替代 MES 通訊
```

---

## 13. Event Topic 設計規範

### 13.1 設計原則

```
Topic = 資料的「位置」（哪台設備、哪種大類）
Payload field = 資料的「內容」（具體是什麼 event type）
不要把「內容」塞到 topic 裡。
```

### 13.2 三種方案比較

| 方案 | Topic 結構 | 優點 | 缺點 |
|---|---|---|---|
| A. 每個 event 一個 topic | `.../Event/ProcessStarted` | 可用 topic 過濾 | Topic 爆炸（100 設備 × 30 event = 3000 topic）|
| B. 一個 event topic | `.../Event` | 最簡單 | 無法用 topic 過濾特定 event 類別 |
| **C. 按大類分（採用）** | `.../Event/Process` | 平衡：可按類訂閱、topic 數可控 | 需定義大類（一次性設計） |

### 13.3 Event 大類定義

| Event 大類 | Topic 尾巴 | 包含的 event_type | 來源 |
|---|---|---|---|
| **Process** | `.../Event/Process` | ProcessStarted, ProcessCompleted, ProcessPaused, ProcessAborted, ProcessResumed | EAP / PLC |
| **Recipe** | `.../Event/Recipe` | RecipeDownloaded, RecipeChanged, RecipeValidated, RecipeApproved | EAP |
| **Lot** | `.../Event/Lot` | LotMoveIn, LotMoveOut, LotHold, LotRelease, LotSplit, LotMerge | MES |
| **Quality** | `.../Event/Quality` | QualityHold, QualityRelease, Disposition, SamplingRequired | MES / QMS |
| **Maintenance** | `.../Event/Maintenance` | PMStarted, PMCompleted, Calibration, PartReplacement | CMMS |

**新增同類的 event type 不需要改 namespace / topic / Schema Type。** 只需在 payload 的 event_type 帶新值。

### 13.4 Event Payload 標準格式

```json
{
  "_meta": {
    "category": "Event",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/Printer",
    "timestamp": "2024-01-15T09:30:00+08:00"
  },
  "data": {
    "event_type": "ProcessStarted",
    "event_category": "Process",
    "lot_id": "LOT-001",
    "recipe_id": "Recipe-A",
    "operator": "Chen"
  }
}
```

不同 event_type 的 payload 欄位可能有差異：
- `ProcessStarted` 有 `lot_id`, `recipe_id`
- `ProcessCompleted` 多了 `duration_seconds`, `result`
- `PMStarted` 有 `pm_type`, `technician`

Schema Type 用 `on_schema_mismatch: "log_and_store"` 處理欄位差異。

### 13.5 Event Schema Type 範例

```yaml
Schema Type: "Equipment_Event_Process"
  decoder: "json"
  timestamp_field: "_meta.timestamp"
  store_raw: true
  on_schema_mismatch: "log_and_store"
  on_new_field: "suggest"
  fields:
    - name: "event_type"
      type: "string"
      extract: true
      persist: true
    - name: "lot_id"
      type: "string"
      extract: true
      persist: true
    - name: "recipe_id"
      type: "string"
      extract: true
      persist: true
    - name: "duration_seconds"
      type: "float"
      extract: true
      persist: true
    - name: "result"
      type: "string"
      extract: true
      persist: true
    - name: "operator"
      type: "string"
      extract: true
      persist: true
```

### 13.6 完整的 Namespace Topic Tree（含 Event）

```
Enterprise
  └── Site
        └── Area
              └── Line
                    └── Equipment
                          ├── [Topic] Telemetry      ← 連續製程參數
                          ├── [Topic] Status          ← 設備狀態（E10）
                          ├── [Topic] Alarm           ← 告警
                          ├── [Topic] Measurement     ← 品質量測
                          ├── [Topic] Event/Process   ← 加工事件
                          ├── [Topic] Event/Recipe    ← Recipe 事件
                          └── [Topic] Event/Maintenance ← 保養事件
              └── MES
                    ├── [Topic] Event/Lot             ← Lot 事件
                    └── [Topic] Event/Quality          ← 品質事件
```

### 13.7 Consumer 訂閱範例

```
# 拿某台設備的所有 event
mqtt sub -t "Enterprise/Site/Area/Line1/Printer/Event/#"

# 拿全廠的 Process event
mqtt sub -t "+/+/+/+/+/Event/Process"

# 拿全廠的所有 event
mqtt sub -t "+/+/+/+/+/Event/#"

# 拿 MES 的 Lot event
mqtt sub -t "+/+/+/MES/Event/Lot"
```

---

## 14. AI/LLM 策略與定位

### 14.1 核心洞察

```
LLM Agent 最大的痛點：不知道資料在哪裡、不知道資料代表什麼。

UNS 剛好解決這兩個問題：
  1. 資料在哪裡 → Namespace Tree（結構化的資料目錄）
  2. 資料代表什麼 → Tag metadata（名稱、單位、type、description）
  3. 資料的脈絡 → Production Context（Lot / Step / Recipe）

沒有 UNS（異質系統直連 AI）：
  每個客戶做一個 custom MCP = SI 專案 = 無法產品化

有 UNS：
  標準化的 API + 結構化的 metadata = AI 可用標準方式存取所有工廠
```

### 14.2 產品定位調整

```
原本：UNS Namespace Data Platform
      「工廠資料的 Single Source of Truth」

調整：UNS Namespace Data Platform + AI-Ready Factory Data Hub
      「工廠資料的 Single Source of Truth + AI 的眼睛和手」

  → 資料住在你這裡（護城河）
  → AI 透過你來理解工廠（差異化）
  → 客戶用什麼 AI 都可以（不被 AI vendor 綁定）

  你不是在賣 AI → 你是在賣「讓 AI 能用的工廠資料平台」
```

### 14.3 五大 AI 應用場景

#### 場景 1：自然語言查詢工廠資料

```
工程師：「Line1 印刷機昨天 Lot-001 加工時的溫度趨勢？」

LLM Agent 動作：
  1. browse_namespace() → 找到 Line1/Printer
  2. list_tags("Line1/Printer") → 找到 temperature tag_id = 42
  3. get_production_run(lot_id="LOT-001") → 找到 start/end time
  4. query_telemetry(tag_id=42, start, end) → 拿到溫度資料
  5. 生成趨勢圖 + 文字摘要

為什麼只有 UNS 能做到：
  沒有 UNS → LLM 要知道資料在哪個 DB、哪張表、哪個 column
  有 UNS → LLM 透過 Namespace Tree 自己找（像人看目錄一樣）
```

#### 場景 2：異常自動診斷

```
系統偵測到 OOS：Lot-001 硬度 = 8.5N（下限 10N）

LLM Agent 自動：
  1. 查 Lot-001 的 production_run → Line1/Printer, Recipe-A
  2. 查加工期間的溫度 → 最後 2 分鐘從 180°C 掉到 165°C
  3. 查設備 event → 發現同時有 CoolingSystemAlarm
  4. 查最近 10 批同產品 → 溫度都穩定在 178-182°C
  5. 生成根本原因分析報告

  → 工程師本來要花 4 小時查三個系統 + 寫 Excel
  → AI 10 秒搞定
```

#### 場景 3：MCP Server — 讓任何 LLM 都能和工廠對話

```
                    ┌─── Claude Desktop
                    │
UNS MCP Server ◄────┼─── Gemini Agent
                    │
                    └─── 企業自建 AI / Dify

不是你做 AI → 而是你讓所有 AI 都能用你的資料
客戶用什麼 LLM 都可以 → 但資料一定在你的 UNS 裡
→ 詳見 §15 MCP Server 設計
```

#### 場景 4：AI Copilot for Factory Engineer

```
內建在 Namespace Manager UI 的 Chat 助手：

  Engineer: 「昨天 OEE 為什麼掉了？」
  AI: 「Line2/Mixer 14:00-16:30 Unscheduled Downtime（MotorOverheat）
       這 2.5 小時拉低整廠 OEE 3.2 個百分點。」

  Engineer: 「那台 Mixer 最近故障頻率有變高嗎？」
  AI: 「過去 30 天平均每週 1.5 次，vs 前 90 天每週 0.3 次。
       建議安排預防性保養。」
```

#### 場景 5：LLM 增強 Schema Auto-detect

```
純規則推斷：
  payload: {"TMP_01": 180.5, "PRS_02": 2.1} → 「2 個 float 欄位」

LLM 增強推斷：
  「TMP_01 看起來是 Temperature（溫度），建議單位 °C
   PRS_02 看起來是 Pressure（壓力），建議單位 kPa」
  → 自動建議 Tag 中文名稱、單位、deadband
  → 管理者只要 confirm，不用自己填
```

### 14.4 AI Phase 規劃

| Phase | AI 功能 | 依賴 |
|---|---|---|
| **Phase 1 (PoC)** | MCP Server 基本版（browse + query）+ AI Demo | UNS API 完成 |
| **Phase 2 (MVP)** | 異常自動診斷 + AI Copilot in UI + Schema LLM 增強 | Production Context 完成 |
| **Phase 3 (Prod)** | 完整 MCP + 多 LLM 支援 + 預測性維護 | 穩定運行 |

### 14.5 PoC Demo 劇本

```
Demo 1「看結構」：拖拉 Namespace Tree → 資料自動流入 → 「哦，可以管理」
Demo 2「看資料」：即時看板 + 歷史查詢 + Retention 設定 → 「哦，有 Historian」
Demo 3「搬設備」：拖拉 Printer Line1→Line2 → 歷史連續 → 「哦！這很酷」
Demo 4「問 AI」：Chat 問搬遷前後溫度差異 → AI 自動查 + 分析 → 「😱 這才是我要的」

  Demo 4 是全場最震撼的一幕。
  但它需要 Demo 1-3 做基礎（沒有 UNS 就沒有標準化 API 給 AI 用）。
```

---

## 15. MCP Server 設計

### 15.1 定位

```
MCP（Model Context Protocol）= 讓 LLM Agent 用標準化方式存取外部工具和資料。
UNS MCP Server = 讓任何 LLM 都能和 UNS 平台互動的橋樑。

不自己做 AI → 讓所有 AI 都能用你的資料。
```

### 15.2 MCP Tools 定義

| Tool | 參數 | 回傳 | 用途 |
|---|---|---|---|
| `browse_namespace` | path (optional) | Namespace 子節點列表 | 瀏覽工廠結構 |
| `list_tags` | node_path | Tag 列表 (name, unit, type) | 列出設備的資料點 |
| `query_telemetry` | tag_ids, start, end | 時間序列資料 | 查歷史趨勢 |
| `get_latest_values` | tag_ids[] | 最新值 + timestamp | 查即時值 |
| `get_production_run` | lot_id or equipment+time | Run 資訊 | 查生產脈絡 |
| `query_events` | equipment, time_range, category | Event 列表 | 查事件紀錄 |
| `search_tags` | keyword | 匹配的 Tag 列表 | 用關鍵字找 Tag |

### 15.3 MCP Resources 定義

| Resource URI | 內容 | 用途 |
|---|---|---|
| `uns://namespace/tree` | 完整 Namespace 結構 (JSON) | LLM 理解工廠全貌 |
| `uns://tags/{tag_id}/metadata` | Tag 定義 (name, unit, type, desc) | LLM 理解資料語義 |
| `uns://equipment/{path}/status` | 設備即時狀態 | LLM 判斷設備健康 |
| `uns://schema-types` | 所有 Schema Type 定義 | LLM 理解 payload 結構 |

### 15.4 MCP Server 架構

```
┌──────────────────────────────────────────────┐
│  LLM Agent（Claude / Gemini / Dify / 自建）  │
└──────────────────┬───────────────────────────┘
                   │ MCP Protocol (stdio / SSE)
                   ▼
┌──────────────────────────────────────────────┐
│  UNS MCP Server (Python)                     │
│                                              │
│  Tools:                                      │
│    browse_namespace → 呼叫 REST API          │
│    list_tags        → 呼叫 REST API          │
│    query_telemetry  → 呼叫 gRPC / REST API   │
│    get_latest       → 呼叫 REST API          │
│    get_prod_run     → 呼叫 REST API          │
│    query_events     → 呼叫 REST API          │
│    search_tags      → 呼叫 REST API          │
│                                              │
│  Resources:                                  │
│    uns://namespace/tree → 快取 + 定期更新     │
│    uns://tags/*/metadata → 即時查詢           │
└──────────────────┬───────────────────────────┘
                   │ REST / gRPC
                   ▼
┌──────────────────────────────────────────────┐
│  UNS Platform Backend (FastAPI)              │
└──────────────────────────────────────────────┘
```

### 15.5 為什麼 MCP Server 是獨立元件

```
不把 MCP 做在 Backend 裡面，而是獨立一個 MCP Server：
  ✅ LLM 可以在使用者本機跑（Claude Desktop）→ MCP Server 也在本機
  ✅ 不同客戶可以選擇不同的 MCP 部署方式
  ✅ MCP Server 可以獨立更新、不影響 Backend
  ✅ 未來可以做多個 MCP Server（不同 LLM 的特化版本）
```

### 15.6 Phase 1 MCP 實作範圍

```
Phase 1（PoC）只做 3 個 Tools：
  ✅ browse_namespace — 瀏覽工廠結構
  ✅ query_telemetry — 查歷史資料
  ✅ get_latest_values — 查即時值

  + 1 個 Resource：
  ✅ uns://namespace/tree — namespace 全貌

  足以支撐 Demo 4「問 AI」的場景。
  其餘 Tools/Resources 在 Phase 2 補上。
```

---

## 16. 術語表

| 術語 | 定義 |
|---|---|
| **Namespace** | MQTT topic tree 的完整階層結構，遵循 ISA-95 |
| **Namespace Node** | 樹上的一個節點，可以是 structural（純階層）或 topic（可收發資料）|
| **Schema Type** | Payload 結構的可重用定義，類似 class |
| **Tag** | 一個獨立的時間序列資料點（如「Line1 印刷機溫度」），擁有永久 tag_id |
| **tag_source_mapping** | MQTT topic → tag_id 的對應關係，可變更 |
| **Persist Mode** | 每個 topic 的持久化策略（db / retain / passthrough）|
| **Deadband** | 值變化量小於此門檻時跳過寫入，減少資料量 |
| **Backfill** | 修改 Schema Type 後，重新掃描 raw payload 補提取歷史資料 |
| **Live Migration** | 移動 namespace node 時自動更新 tag_source_mapping，歷史資料不中斷 |
| **Auto-detect** | 自動偵測未定義 topic 的 payload 結構，產生 Schema Type 建議 |
| **Production Context** | 把 IoT 資料和 MES 的 Lot / Step / Recipe 關聯 |
| **EAV** | Entity-Attribute-Value 模式：每個參數值一筆 row（vs 每個參數一個 column）|
| **Command Flow** | MES 對設備下命令的流程；命令走直接通道，UNS 記錄 event |
| **Event Category** | Event topic 的大類分法（Process / Recipe / Lot / Quality / Maintenance）|
| **MCP** | Model Context Protocol：讓 LLM Agent 標準化存取外部工具/資料的協議 |
| **MCP Server** | UNS 平台的 MCP 介面，讓任何 LLM 都能查詢工廠資料 |
| **AI-Ready** | 資料具有結構化目錄 + 語義化 metadata + 標準化 API，AI 可直接使用 |
