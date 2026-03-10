# UNS 架構設計決策紀錄

> 此文件記錄 UNS (Unified Namespace) 架構在實務導入時的關鍵設計決策、
> 技術選型、以及業界實踐的分析。涵蓋 ISA-95 L0–L4 全層級的資料交換策略。

---

## 1. UNS 的本質與定位

### UNS 是什麼

UNS 是一個**架構模式 (architectural pattern)**，不是一個協議或產品。  
核心價值：**統一的命名規範 + event-driven 資料的單一存取點。**

### UNS 不是什麼

- ❌ 不是「所有資料都走 MQTT」
- ❌ 不是 Single Source of Truth（是 Single Point of Access）
- ❌ 不能取代 MES、ERP、Historian 的商業邏輯
- ❌ 不適合處理 request/response 交易

### Walker Reynolds (4.0 Solutions) 觀點的適用範圍

| 他的主張 | 現實 |
|---|---|
| 整合 L0-L4 所有東西 | 主要解決 L0-L2 event-driven 資料 |
| 全部走 MQTT | MQTT + gRPC 各司其職 |
| Single Source of Truth | Single Point of Access |

> **UNS 最大的商業價值：讓工廠的資料架構從 point-to-point spaghetti 變成 hub-and-spoke 模式。**

---

## 2. 技術選型：三件套

```
┌─────────────────────────────────────────────────┐
│               UNS（統一資料模型）                  │
│                                                 │
│   ┌──────────────┐        ┌──────────────────┐  │
│   │    MQTT       │        │      gRPC        │  │
│   │               │        │                  │  │
│   │  L0-L2 設備   │        │  L2-L4 系統      │  │
│   │  pub/sub      │        │  req/res         │  │
│   │               │        │                  │  │
│   │  Telemetry    │        │  Command 指令    │  │
│   │  Status       │        │  Config 配方     │  │
│   │  Alarm        │        │  Batch 批次      │  │
│   │  Event        │        │  MasterData 同步 │  │
│   │  Metrics      │        │  Query 查詢      │  │
│   └──────┬───────┘        └────────┬─────────┘  │
│          │                         │             │
│          ▼                         ▼             │
│   ┌────────────────────────────────────────┐     │
│   │         TimescaleDB (持久化層)          │     │
│   │  tags (維度) + ts_* (時序資料)          │     │
│   └────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

### 為什麼選這三個？

| 技術 | 角色 | 為什麼不用其他的 |
|---|---|---|
| **MQTT** | L0-L2 設備資料 pub/sub | PLC/Gateway 幾乎都支援 MQTT |
| **gRPC** | L2-L4 系統間 req/res | protobuf 強型別合約 + 自動 code gen |
| **TimescaleDB** | 時序歷史資料 | PostgreSQL 相容 + `time_bucket()` + hypertable |

### 被排除的技術

| 技術 | 排除原因 |
|---|---|
| GraphQL | MES 查詢模式固定，不需要前端自由組合的彈性 |
| IBM MQ | gRPC + Transaction Log 可覆蓋，省掉 MQ 授權成本 |
| NATS JetStream | 技術優秀但在 OT 無生態系，PLC/Gateway 不支援 |
| REST API | gRPC 效能更好、有強型別合約 |
| Kafka | 太重，運維成本高，適合大規模場景 |

---

## 3. Payload 標準化策略

### 分層標準

| 區塊 | 適用層級 | 標準化程度 |
|---|---|---|
| **Part A** | L0–L2 | ✅ 嚴格標準（Telemetry/Status/Alarm 格式完全固定） |
| **Part B** | L2–L4 | 📨 僅信封標準（`_meta` 固定，`data` 自定義） |

### 信封格式 (`_meta`)

```json
{
  "_meta": {
    "category": "Telemetry",
    "schema_version": "1.0",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/Printer",
    "timestamp": "2024-01-15T08:30:00+08:00",
    "quality": "good"
  },
  "data": { ... }
}
```

> **L0-L2 可以統一，因為物理量是通用的（溫度就是 float + 單位）。
> L2-L4 只能統一信封，因為商業邏輯各家不同。**

---

## 4. MQTT 不適合 Request/Response

### 核心問題

MQTT 是 pub/sub 協議，天生設計用於「事件通知」，不是「請求回應」。  
在 MQTT 上實作 correlation_id + reply_to + timeout 是**用 pub/sub 模擬 RPC — 反模式**。

### 解決方案

| 資料性質 | 協議 | 原因 |
|---|---|---|
| Event-driven（有事發生了）| MQTT | pub/sub 天生適合 |
| Request/Response（幫我做事）| gRPC | HTTP/2 天生就是 req/res |

### gRPC 的 response 就是 ACK

不需要 MQTT 的 correlation_id / reply_to / timeout / Transaction Log。  
gRPC 回 `success=true` 就是 ACK，回 `success=false` 就是 NACK。

---

## 5. Consumer 離線與訊息可靠性

### 問題

MQTT Broker 不是 Queue。Consumer 死了，訊息丟失。

### 解法

- **L0-L2 Telemetry**：掉就掉，高頻資料丟一筆無影響
- **L0-L2 Status**：Retained message 保證最新狀態
- **L3-L4 交易**：走 gRPC，不走 MQTT，沒有這個問題
- **L3-L4 事件通知**：透過 CDC + Outbox Pattern 保證不丟

---

## 6. Time-Series DB 設計

### 核心原則

1. **Tag 身份與 MQTT 來源分離**（參考 OSIsoft PI 設計）
2. **`asset_path` 字串就是最好的階層表達**，不用 parent_id 樹
3. **每種 Category 各自一張表**，欄位結構不同
4. **Category 層是「資產位置」與「資料分類」的分界線**

### 表結構

```
tags                          → 穩定身份（tag_id 永不改變）
tag_source_mapping            → MQTT topic → tag_id 映射（OT 可改）
tag_change_log                → 變更紀錄（audit）
ts_telemetry                  → 數值感測（value DOUBLE）
ts_status                     → 設備狀態（state TEXT）
ts_alarms                     → 告警紀錄（severity, code, message）
ts_events                     → 製程事件（event_code, details JSONB）
ts_metrics                    → 聚合指標（values JSONB）
```

### Topic 改名的處理

**問題**：OT 改了 MQTT topic（產線改名），DB 的歷史資料怎麼辦？

**解法**：`tag_source_mapping` 表分離身份與來源。Topic 改了，只更新 mapping，`tag_id` 不動，歷史資料自動跟著。

| 場景 | 操作 |
|---|---|
| **A. 理想**：管理員先知道 | `remap_topic()` — 先改 mapping，再改設備 |
| **B. 實務**：OT 先改了 | `merge_tags()` — 事後合併新建的 tag 回舊 tag |

---

## 7. L3-L4 系統與 UNS 的整合模式

### Command-Event 分離

```
Command（做事）：  OPI ──gRPC──► MES ──► MES DB       ← Source of Truth
Event  （廣播）：              MES ──MQTT──► UNS       ← 即時通知 + 歷史紀錄
```

- **gRPC 負責「做事」**（交易、指令、確認）
- **MQTT 負責「廣播結果」**（告訴全世界發生了什麼）
- **MES DB 是 Source of Truth**
- **UNS/TimescaleDB 是歷史副本 + 即時通知通道**

### MES 事件如何進入 UNS？

三種方式（推薦 CDC）：

| 方式 | MES 改動 | 可靠性 | 推薦 |
|---|---|---|---|
| 直接在 code 裡加 `mqtt.publish()` | 改幾行 | ⚠️ | POC |
| Outbox Pattern（掃 event table） | 加一個欄位 | ✅ | Production |
| **CDC (Debezium)** | **零改動** | ✅ | **推薦** |

### CDC 的價值

- 不需要改 MES 任何一行程式碼
- 不需要跟 MES 工程師溝通 coding rule
- 只需要看懂 MES DB schema，寫 transform rules
- 零侵入接入任何既有系統

---

## 8. 資料查詢架構

### Data Access Service

L2-L4 系統查詢歷史資料時，透過 gRPC Data Access Service，不直接查 DB：

```
L2/L3/L4 系統 ──gRPC──► Data Access Service ──SQL──► TimescaleDB
                       （翻譯層：asset_path → tag_id → SQL 查詢）
```

### 查詢服務核心 API

| gRPC Method | 用途 |
|---|---|
| `BrowseAssets()` | 瀏覽資產樹（Dashboard 導航） |
| `ListTags()` | 某 asset 底下有哪些 tag |
| `QueryTelemetry()` | 查溫度/壓力/速度歷史 |
| `QueryStatusHistory()` | 查設備狀態歷史 |
| `QueryAlarms()` | 查告警歷史 |
| `QueryEvents()` | 查製程事件歷史 |
| `QueryMetrics()` | 查 OEE/良率趨勢 |

---

## 9. 其他可實作 UNS 的技術（備查）

| 技術 | 優勢 | 在 OT 的成熟度 |
|---|---|---|
| MQTT | 輕量、設備支援最廣 | ✅✅ |
| Kafka | 持久化、Consumer 離線不丟 | ⚠️ |
| NATS JetStream | 輕量 + 持久化 + 原生 Req/Reply | ❌ |
| OPC UA Pub/Sub | 自帶資料語義 | ✅ |

> MQTT 不是最先進的選擇，但目前 OT 生態系只認 MQTT 和 OPC UA。

---

## 10. 相關檔案索引

| 檔案 | 內容 |
|---|---|
| `payload_standard_spec.md` | 9 種 Category 的 Payload 標準規格 |
| `timeseries_schema.sql` | TimescaleDB 建庫腳本 |
| `consumer_example.py` | MQTT Consumer + TagAdmin 管理操作 |
| `namespace_template.yaml` | ISA-95 Topic Tree 模板 |
| `topic_naming_guide.md` | Topic 命名規範 |
| `cdc_mes_bridge/` | Debezium CDC 範例（MES DB → UNS） |
| `production_context_schema.sql` | Production Run 表 + ts_* 欄位擴展 |
| `production_context_consumer.py` | 雙模式 Consumer（Continuous + Commanded/EAP） |
| `measurement_and_state_schema.sql` | Measurement Data + Equipment State + OEE View |
| `ops/` | 運維工具（retention、歸檔、Mosquitto、DB 安全、監控、Schema Registry） |

---

## 11. 安全性 (Security)

### 11.1 MQTT Broker — 設備級認證 + ACL

每台設備一個 MQTT user，透過 ACL 限制可存取的 topic。
認證方式：username/password（未來可升級為 X.509 client certificate）。

#### Mosquitto ACL 設定範例

```
# /etc/mosquitto/acl.conf

# ─── 設備端（每台設備一個 user） ───────────────────────────
# 印刷機：只能 publish 自己的 Telemetry/Status/Alarm
user printer-line1
topic write TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Telemetry/#
topic write TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Status/#
topic write TaiwanPrecision/Taoyuan/SMT/Line1/Printer/Alarm/#
# 設備不能訂閱任何 topic（防止竊聽其他設備資料）
# 設備不能 publish 到 Command topic（防止冒充指令）

# 貼片機
user pickandplace-line1
topic write TaiwanPrecision/Taoyuan/SMT/Line1/PickAndPlace/Telemetry/#
topic write TaiwanPrecision/Taoyuan/SMT/Line1/PickAndPlace/Status/#
topic write TaiwanPrecision/Taoyuan/SMT/Line1/PickAndPlace/Alarm/#

# 迴焊爐
user reflowoven-line1
topic write TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Telemetry/#
topic write TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Status/#
topic write TaiwanPrecision/Taoyuan/SMT/Line1/ReflowOven/Alarm/#


# ─── UNS Consumer（只讀） ──────────────────────────────────
user uns-consumer-01
topic read TaiwanPrecision/#
# Consumer 不能 publish（防止資料回寫汙染）

user uns-consumer-02
topic read TaiwanPrecision/#


# ─── CDC Transform Service ─────────────────────────────────
# 只能 publish MES 事件（Event/Status），來源是 MES DB
user cdc-transform-01
topic write TaiwanPrecision/+/+/+/+/Event/#
topic write TaiwanPrecision/+/+/+/+/Status/#


# ─── 管理員（全權限，僅供維運/除錯） ──────────────────────
user uns-admin
topic readwrite #
```

#### Mosquitto 密碼檔設定

```bash
# 建立密碼檔
mosquitto_passwd -c /etc/mosquitto/passwords printer-line1
mosquitto_passwd    /etc/mosquitto/passwords pickandplace-line1
mosquitto_passwd    /etc/mosquitto/passwords reflowoven-line1
mosquitto_passwd    /etc/mosquitto/passwords uns-consumer-01
mosquitto_passwd    /etc/mosquitto/passwords cdc-transform-01
mosquitto_passwd    /etc/mosquitto/passwords uns-admin
```

#### Mosquitto Broker 主設定

```
# /etc/mosquitto/mosquitto.conf

# 關閉匿名存取
allow_anonymous false

# 密碼認證
password_file /etc/mosquitto/passwords

# ACL 授權
acl_file /etc/mosquitto/acl.conf

# TLS 加密（port 8883）
listener 8883
cafile   /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile  /etc/mosquitto/certs/server.key
tls_version tlsv1.3

# 保留 port 1883 僅供 localhost 開發使用
listener 1883 127.0.0.1
```

> **未來擴充：X.509 Client Certificate**
>
> 當客戶有 PKI 基礎設施時，可改為 X.509 認證，每台設備用自己的 client certificate：
> ```
> # mosquitto.conf 加入：
> require_certificate true
> use_identity_as_username true   # CN 欄位作為 username → ACL 沿用
> ```
> ACL 規則不需要改，因為 CN 就是 username（如 `printer-line1`）。

### 11.2 gRPC 安全

| 層面 | 機制 | 說明 |
|---|---|---|
| **傳輸加密** | mTLS (mutual TLS) | client 和 server 互相驗證 certificate |
| **認證** | JWT token（短期）或 mTLS client cert（長期） | MES/OPI 用 JWT，Data Access Service 用 mTLS |
| **授權** | gRPC interceptor + RBAC | 不同角色可呼叫的 RPC method 不同 |

```python
# gRPC server 端 TLS 設定
import grpc

server_creds = grpc.ssl_server_credentials(
    [(private_key, certificate_chain)],
    root_certificates=ca_cert,
    require_client_auth=True   # mTLS：要求 client 也出示 cert
)
server.add_secure_port("[::]:50051", server_creds)
```

#### gRPC RBAC 角色設計

| 角色 | 可呼叫的 RPC | 典型使用者 |
|---|---|---|
| `operator` | `LotMoveIn`, `LotMoveOut` | OPI 操作員介面 |
| `engineer` | 所有 operator + `UpdateRecipe`, `SetParameter` | 製程工程師 |
| `readonly` | `BrowseAssets`, `QueryTelemetry`, `QueryAlarms` | Dashboard / BI |
| `admin` | 全部 | 系統管理員 |

### 11.3 TimescaleDB 安全

```sql
-- 建立 3 個不同權限的 DB role
CREATE ROLE uns_writer   LOGIN PASSWORD '...' ;   -- Consumer 用
CREATE ROLE uns_reader   LOGIN PASSWORD '...' ;   -- Data Access Service 用
CREATE ROLE uns_admin    LOGIN PASSWORD '...' ;   -- 管理操作用

-- uns_writer：只能 INSERT（Consumer 寫入用）
GRANT INSERT ON ts_telemetry, ts_status, ts_alarms, ts_events, ts_metrics TO uns_writer;
GRANT SELECT, INSERT, UPDATE ON tags, tag_source_mapping, tag_change_log TO uns_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO uns_writer;

-- uns_reader：只能 SELECT（Query Service 用）
GRANT SELECT ON ALL TABLES IN SCHEMA public TO uns_reader;

-- uns_admin：全權限（TagAdmin 操作用）
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO uns_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO uns_admin;
```

### 11.4 網路架構（單廠區 Purdue Model）

```
  ┌─────────────────────────────────────────────────────────────┐
  │  L4/L5  企業網路 (IT)                                       │
  │                                                             │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │
  │  │ Dashboard │  │ BI Tool  │  │  ERP (SAP / Oracle)      │  │
  │  │ (Browser) │  │          │  │                          │  │
  │  └─────┬─────┘  └─────┬────┘  └────────────┬─────────────┘  │
  │        │              │                     │                │
  │        └──────────────┴──────────┬──────────┘                │
  │                                  │ gRPC (TLS)                │
  └──────────────────────────────────┼───────────────────────────┘
                                     │
  ═══════════════ DMZ / Firewall ════╪════════════════════════════
                                     │
  ┌──────────────────────────────────┼───────────────────────────┐
  │  L3  製造營運 (MES/UNS)          │                           │
  │                                  ▼                           │
  │  ┌──────────────────────────────────────────────────┐       │
  │  │           UNS Core Server                        │       │
  │  │                                                  │       │
  │  │  MQTT Broker    :8883 (TLS)  ← 設備 publish     │       │
  │  │  gRPC Services  :50051 (mTLS) ← OPI/MES/Query   │       │
  │  │  TimescaleDB    :5432 (SSL)  ← Consumer/Query   │       │
  │  │  CDC Transform  (internal)   ← Debezium events  │       │
  │  └────────────────────┬─────────────────────────────┘       │
  │                       │                                      │
  │  ┌───────────┐  ┌─────┴──────┐  ┌──────────┐               │
  │  │ MES Server│  │ OPI Client │  │CDC/Kafka │               │
  │  │ (gRPC)    │  │ (gRPC)     │  │(內部通訊) │               │
  │  └───────────┘  └────────────┘  └──────────┘               │
  └──────────────────────────────────┼───────────────────────────┘
                                     │
  ═══════════════ Firewall ══════════╪════════════════════════════
                                     │ MQTT (TLS 8883)
  ┌──────────────────────────────────┼───────────────────────────┐
  │  L0-L2  車間 (OT)                │                           │
  │                                  │                           │
  │  ┌──────────┐  ┌──────────┐  ┌──┴───────┐                  │
  │  │  PLC     │  │  SCADA   │  │  Edge    │                  │
  │  │  HMI     │  │  DCS     │  │  Gateway │                  │
  │  │          │  │          │  │ (Kepware)│                  │
  │  └──────────┘  └──────────┘  └──────────┘                  │
  │                                                             │
  │  ⚠ OT 網路不可直接連 IT 網路                                  │
  │  ⚠ 所有對外通訊只經過 MQTT TLS 8883                          │
  └─────────────────────────────────────────────────────────────┘
```

#### 防火牆規則摘要

| 方向 | 來源 | 目標 | Port | 說明 |
|---|---|---|---|---|
| OT → L3 | Edge Gateway | MQTT Broker | 8883 (TLS) | 設備資料上傳 |
| L3 → L3 | OPI / MES | gRPC Services | 50051 (mTLS) | 交易操作 |
| L3 → L3 | Consumer | TimescaleDB | 5432 (SSL) | 資料寫入 |
| L4 → L3 | Dashboard / BI | gRPC Query | 50051 (mTLS) | 歷史查詢 |
| L3 → L4 | CDC Transform | MQTT Broker | 8883 | MES 事件廣播 |
| ❌ 禁止 | IT (L4) | OT (L0-L2) | - | 不可穿透 |
| ❌ 禁止 | 外部網路 | 任何 | - | 不可直接存取 |

---

## 12. 資料保留與合規 (Data Retention & Compliance)

### 12.1 可配置的保留策略

保留策略透過 YAML 設定檔管理，每個部署環境可覆寫預設值：

```yaml
# retention_policy.yaml — 資料保留策略設定

retention:
  # ── 每種 Category 的保留期限 ──────────────────────────
  
  telemetry:
    raw:           30d      # 原始資料（每秒/每 5 秒）
    downsampled:            # 降取樣保留
      1min_avg:    365d     # 1 分鐘平均
      1hr_avg:     1825d    # 1 小時平均 (5 年)
    on_expiry:     archive  # archive | delete

  status:
    raw:           365d     # 狀態變更紀錄（低頻，不佔空間）
    downsampled:   ~        # 不降取樣
    on_expiry:     archive

  alarm:
    raw:           1825d    # 5 年（法規要求）
    downsampled:   ~
    on_expiry:     archive  # 告警紀錄不可直接刪除

  event:
    raw:           1825d    # 5 年（traceability）
    downsampled:   ~
    on_expiry:     archive

  metrics:
    raw:           730d     # 2 年
    downsampled:   ~
    on_expiry:     delete   # OEE 歷史超期可直接刪


  # ── Cold Storage 歸檔設定 ────────────────────────────
  
  archive:
    enabled:       true
    backend:       s3       # s3 | nas | minio
    s3:
      bucket:      uns-archive
      region:      ap-northeast-1
      prefix:      "{enterprise}/{site}/{year}/{month}/"
    nas:
      mount_path:  /mnt/archive/uns
      path_format: "{enterprise}/{site}/{year}/{month}/"
    
    format:        parquet  # parquet | csv
    compression:   snappy   # snappy | gzip | none
    
    # 歸檔完成後是否從 TimescaleDB 刪除
    delete_after_archive: true
```

### 12.2 TimescaleDB 保留策略實作

```sql
-- ═══════════════════════════════════════════════════════════════
-- 1. 自動保留策略：超期資料自動移除
-- ═══════════════════════════════════════════════════════════════

-- Telemetry：保留 30 天原始資料
SELECT add_retention_policy('ts_telemetry', INTERVAL '30 days');

-- Status：保留 1 年
SELECT add_retention_policy('ts_status', INTERVAL '365 days');

-- Alarm：保留 5 年
SELECT add_retention_policy('ts_alarms', INTERVAL '1825 days');

-- Event：保留 5 年
SELECT add_retention_policy('ts_events', INTERVAL '1825 days');

-- Metrics：保留 2 年
SELECT add_retention_policy('ts_metrics', INTERVAL '730 days');


-- ═══════════════════════════════════════════════════════════════
-- 2. 降取樣：Continuous Aggregate
-- ═══════════════════════════════════════════════════════════════

-- 1 分鐘平均（保留 1 年）
CREATE MATERIALIZED VIEW telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    tag_id,
    AVG(value)   AS avg_value,
    MIN(value)   AS min_value,
    MAX(value)   AS max_value,
    COUNT(*)     AS sample_count
FROM ts_telemetry
GROUP BY bucket, tag_id;

-- 自動刷新：每小時計算過去 2 小時的 1min 聚合
SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset    => INTERVAL '2 hours',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- 1min 聚合保留 1 年
SELECT add_retention_policy('telemetry_1min', INTERVAL '365 days');


-- 1 小時平均（保留 5 年）
CREATE MATERIALIZED VIEW telemetry_1hr
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', bucket) AS bucket,
    tag_id,
    AVG(avg_value) AS avg_value,
    MIN(min_value) AS min_value,
    MAX(max_value) AS max_value,
    SUM(sample_count) AS sample_count
FROM telemetry_1min
GROUP BY time_bucket('1 hour', bucket), tag_id;

SELECT add_continuous_aggregate_policy('telemetry_1hr',
    start_offset    => INTERVAL '3 hours',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

SELECT add_retention_policy('telemetry_1hr', INTERVAL '1825 days');


-- ═══════════════════════════════════════════════════════════════
-- 3. 查詢時自動選擇最佳精度
-- ═══════════════════════════════════════════════════════════════

-- Data Access Service 的查詢邏輯：
--   根據查詢的時間範圍自動選表：
--   - 最近 30 天 → ts_telemetry（原始資料）
--   - 30 天 ~ 1 年 → telemetry_1min（1 分鐘平均）
--   - 1 年以上    → telemetry_1hr（1 小時平均）
--
-- 也可讓呼叫端在 gRPC request 中指定 resolution：
--   QueryTelemetryRequest {
--       resolution: RAW | ONE_MINUTE | ONE_HOUR | AUTO
--   }
```

### 12.3 Cold Storage 歸檔流程

```
  TimescaleDB                歸檔程式               Cold Storage
  ┌──────────┐              ┌──────────┐           ┌──────────┐
  │ 超期資料  │──── 匯出 ───►│ 轉 Parquet│──── 上傳 ►│ S3 / NAS │
  │          │              │ + 壓縮    │           │          │
  │          │◄── 確認 ─────│ 驗證完整性 │           │ 按 年/月  │
  │ 刪除原始  │              │          │           │ 目錄歸檔  │
  └──────────┘              └──────────┘           └──────────┘
```

```python
# 歸檔腳本概念（每月執行一次）

def archive_expired_data(category: str, retention_days: int, config: dict):
    """
    1. 查詢超期資料
    2. 匯出為 Parquet
    3. 上傳到 S3/NAS
    4. 驗證完整性（row count 比對）
    5. 從 TimescaleDB 刪除已歸檔的 chunks
    """
    cutoff = datetime.now() - timedelta(days=retention_days)
    
    # 匯出
    df = pd.read_sql(
        f"SELECT * FROM ts_{category} WHERE time < %s",
        db_conn, params=[cutoff]
    )
    
    # 寫 Parquet
    parquet_path = f"{config['prefix']}/{category}/{cutoff.strftime('%Y/%m')}.parquet"
    df.to_parquet(parquet_path, compression=config['compression'])
    
    # 上傳（依 backend 不同）
    if config['backend'] == 's3':
        s3_client.upload_file(parquet_path, config['s3']['bucket'], parquet_path)
    elif config['backend'] == 'nas':
        shutil.copy(parquet_path, f"{config['nas']['mount_path']}/{parquet_path}")
    
    # 驗證
    archived_count = pq.read_metadata(parquet_path).num_rows
    assert archived_count == len(df), "歸檔資料筆數不符！"
    
    # 刪除已歸檔的 TimescaleDB chunks
    # (TimescaleDB 的 drop_chunks 比 DELETE 高效得多)
    select_drop_chunks(f'ts_{category}', older_than=cutoff)
    
    logger.info(f"已歸檔 {category}: {archived_count} 筆 → {parquet_path}")
```

### 12.4 合規要求對照表

#### FDA 21 CFR Part 11（製藥業適用）

| 要求 | UNS 架構的對應機制 |
|---|---|
| **電子簽章** | gRPC interceptor 記錄 `operator_id` + 時間戳 |
| **Audit Trail（稽核軌跡）** | `tag_change_log` 表記錄所有變更；TimescaleDB 只寫不改（append-only） |
| **資料完整性** | TimescaleDB hypertable + Parquet 歸檔皆不可竄改 |
| **存取控制** | DB 三角色分離（writer/reader/admin）+ MQTT ACL |
| **系統驗證** | 部署文件需包含 IQ/OQ/PQ 驗證報告（此架構不處理） |
| **備份與恢復** | PostgreSQL WAL 串流複寫 + S3 歸檔雙重備份 |

> **注意**：FDA 21 CFR Part 11 要求的「電子簽章」不是一般的登入密碼。
> 是操作員在**每次關鍵操作**（如批次放行、配方修改）時，必須輸入的 **username + password + 理由**。
> 這個邏輯由 MES/OPI 應用層實作，UNS 負責記錄和歸檔。

#### IATF 16949（汽車業適用）

| 要求 | UNS 架構的對應機制 |
|---|---|
| **品質紀錄保留** | Event 和 Alarm 保留 ≥ 產品壽命 + 1 年（retention_policy.yaml 可配置） |
| **產品 Traceability** | `ts_events` 表的 `event_code` + `details` JSONB 記錄每個批次的完整歷程 |
| **SPC 數據** | `ts_telemetry` 的降取樣聚合（1min/1hr）提供長期趨勢分析 |
| **8D 問題追溯** | Data Access Service 的 `QueryEvents` + `QueryAlarms` 提供時間範圍查詢 |
| **供應商追溯** | MasterData category（透過 gRPC 同步）記錄物料批號來源 |

#### 半導體 Traceability

| 要求 | UNS 架構的對應機制 |
|---|---|
| **Lot 歷程追溯** | CDC 捕捉 MES `event_tracking` 表 → UNS Event → TimescaleDB |
| **製程參數紀錄** | Telemetry 原始資料保留 30 天，降取樣保留 5 年 |
| **設備狀態對照** | `ts_status` 可與 `ts_events` 做時間關聯查詢 |
| **告警紀錄** | `ts_alarms` 保留 5 年，含 severity/code/message |
| **配方版本** | Config category（透過 gRPC）記錄配方下載 + 版本號 |

### 12.5 資料生命週期總覽

```
  資料產生                                                    資料歸檔
  ┌───┐     ┌──────────────┐     ┌────────────────┐     ┌──────────┐
  │設備│────►│  TimescaleDB  │────►│  Continuous    │────►│ S3 / NAS │
  │   │     │              │     │  Aggregate     │     │ (Parquet) │
  └───┘     │  原始資料     │     │               │     │          │
            │  30 天        │     │  1min: 1 年   │     │  超期資料 │
            │              │     │  1hr:  5 年   │     │  永久保存 │
            └──────────────┘     └────────────────┘     └──────────┘
            
   T+0          T+30d              T+365d / T+5yr         T+5yr+
   寫入          自動刪除原始         自動刪除降取樣          歸檔保存
               （或歸檔後刪除）      （或歸檔後刪除）
```

---

## 13. 監控與可觀測性 (Observability)

> 系統上線後，你需要回答三個問題：
> 1. **系統有沒有活著？**（Health）
> 2. **系統跑得好不好？**（Performance）
> 3. **出事了能不能查到原因？**（Debugging）

### 13.1 監控架構

```
  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │ MQTT Broker│  │  Consumer  │  │  CDC Pipe  │  │TimescaleDB │
  │ (Mosquitto)│  │  (Python)  │  │ (Debezium) │  │            │
  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    Prometheus                               │
  │  (每 15 秒 scrape 各元件的 /metrics endpoint)               │
  └──────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                       Grafana                                │
  │  Dashboard + 告警規則 (Alert Rules)                           │
  └──────────────────────────────────────────────────────────────┘
```

### 13.2 監控指標定義

#### MQTT Broker（Mosquitto）

Mosquitto 內建 `$SYS` topic 可用 [mosquitto-exporter](https://github.com/sapcc/mosquitto-exporter) 轉為 Prometheus metrics。

| 指標 | Prometheus Metric | 告警閾值 | 說明 |
|---|---|---|---|
| 連線中的 client 數 | `mosquitto_clients_connected` | < 預期設備數 | 設備掉線 |
| 每秒收到的訊息數 | `mosquitto_messages_received_1min` | = 0 持續 5 分鐘 | 所有設備都沒送資料 |
| 每秒發送的訊息數 | `mosquitto_messages_sent_1min` | = 0 持續 5 分鐘 | Consumer 可能死了 |
| Retained message 數 | `mosquitto_retained_messages_count` | > 10000 | 可能有 topic 爆炸 |
| Inflight 訊息數 | `mosquitto_publish_messages_sent` | 持續增長 | 送不出去，Consumer lag |
| 被拒絕的連線 | `mosquitto_connections_rejected` | > 0 | 認證失敗（密碼錯誤/ACL 違規） |

```yaml
# Prometheus scrape config
scrape_configs:
  - job_name: "mosquitto"
    static_configs:
      - targets: ["mosquitto-exporter:9234"]
```

#### UNS Consumer（自訂 metrics）

Consumer 需要在 Python 程式中暴露 Prometheus metrics。用 `prometheus_client` 套件：

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# ── Counters（累計） ──
messages_total = Counter(
    "uns_consumer_messages_total",
    "收到的 MQTT 訊息總數",
    ["category"]   # label: Telemetry / Status / Alarm / ...
)

messages_errors = Counter(
    "uns_consumer_messages_errors_total",
    "處理失敗的訊息數",
    ["category", "error_type"]  # error_type: parse_error / db_error / unknown_category
)

# ── Histograms（延遲分佈） ──
processing_duration = Histogram(
    "uns_consumer_processing_seconds",
    "每筆訊息的處理時間",
    ["category"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

# ── Gauges（目前狀態） ──
active_tags = Gauge(
    "uns_consumer_active_tags",
    "目前 active 的 tag 數量"
)

db_connection_status = Gauge(
    "uns_consumer_db_connected",
    "TimescaleDB 連線狀態 (1=connected, 0=disconnected)"
)

# 啟動 metrics HTTP server（port 8000）
start_http_server(8000)
```

| 指標 | 告警閾值 | 說明 |
|---|---|---|
| `uns_consumer_messages_total` rate = 0 | 持續 5 分鐘 | Consumer 沒在收訊息 |
| `uns_consumer_messages_errors_total` rate > 10/min | 持續 3 分鐘 | 大量處理錯誤 |
| `uns_consumer_processing_seconds` p99 > 0.5s | 持續 5 分鐘 | Consumer 處理太慢 |
| `uns_consumer_db_connected` = 0 | 立即 | DB 連線斷了 |

```yaml
# Prometheus scrape config
  - job_name: "uns-consumer"
    static_configs:
      - targets: ["uns-consumer:8000"]
```

#### CDC Pipeline（Debezium）

Debezium 內建 JMX metrics，用 [jmx-exporter](https://github.com/prometheus/jmx_exporter) 轉 Prometheus。

| 指標 | 告警閾值 | 說明 |
|---|---|---|
| `debezium_metrics_MilliSecondsBehindSource` | > 60000 (1 min) | CDC 延遲超過 1 分鐘 |
| `debezium_metrics_NumberOfEventsFiltered` | 持續增長 | 大量事件被過濾（檢查 filter 設定） |
| `debezium_metrics_NumberOfErroneousEvents` | > 0 | 解析 MES DB WAL 失敗 |
| `debezium_metrics_Connected` | = false | Debezium 與 MES DB 斷線 |

#### TimescaleDB

用 `postgres_exporter` 暴露 PostgreSQL / TimescaleDB metrics。

| 指標 | 告警閾值 | 說明 |
|---|---|---|
| `pg_database_size_bytes` | > 80% 碟碟空間 | 容量即將滿 |
| `pg_stat_activity_count` | > max_connections × 0.8 | 連線快用完 |
| hypertable chunk 數量 | > 1000 per table | 需要調整 chunk_time_interval |
| Continuous Aggregate lag | > 2× refresh_interval | 聚合計算跟不上 |

```yaml
# Prometheus scrape config
  - job_name: "timescaledb"
    static_configs:
      - targets: ["postgres-exporter:9187"]
```

### 13.3 Grafana Dashboard 設計

建議建立 4 個 Dashboard：

| Dashboard | 用途 | 關鍵面板 |
|---|---|---|
| **UNS Overview** | 全局概覽 | 活躍設備數、訊息 throughput、error rate、DB size |
| **MQTT Broker** | Broker 健康 | 連線數趨勢、訊息 rate by topic、ACL reject 事件 |
| **Consumer Performance** | Consumer 處理效能 | 處理延遲 p50/p95/p99、各 category throughput、error breakdown |
| **CDC Pipeline** | CDC 健康 | Source lag、event rate、error count、transform latency |

### 13.4 告警規則（Alertmanager）

```yaml
# prometheus-alerts.yml

groups:
  - name: uns_critical
    rules:
      # ── 設備離線 ──
      - alert: MQTTClientDisconnected
        expr: mosquitto_clients_connected < 5   # 預期設備數
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MQTT 活躍設備數低於預期"

      # ── Consumer 停止 ──
      - alert: ConsumerNotProcessing
        expr: rate(uns_consumer_messages_total[5m]) == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "UNS Consumer 超過 5 分鐘沒處理任何訊息"

      # ── DB 快滿了 ──
      - alert: TimescaleDBDiskFull
        expr: pg_database_size_bytes / node_filesystem_size_bytes > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "TimescaleDB 磁碟使用超過 80%"

      # ── CDC 延遲 ──
      - alert: CDCLagHigh
        expr: debezium_metrics_MilliSecondsBehindSource > 60000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CDC pipeline 延遲超過 1 分鐘"

      # ── 大量錯誤 ──
      - alert: ConsumerHighErrorRate
        expr: rate(uns_consumer_messages_errors_total[5m]) > 10
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "UNS Consumer 錯誤率過高"
```

### 13.5 日誌 (Logging) 策略

| 元件 | 日誌框架 | 日誌等級 | 儲存位置 |
|---|---|---|---|
| Consumer | Python `logging` | INFO（Production）/ DEBUG（除錯） | stdout → Loki / ELK |
| CDC Transform | Python `logging` | INFO | stdout → Loki / ELK |
| MQTT Broker | Mosquitto log | warning + error | /var/log/mosquitto/ |
| TimescaleDB | PostgreSQL log | warning + error | pg_log/ |

> **結構化日誌**：所有 Python 元件建議使用 JSON 格式日誌，方便 Loki/ELK 解析：
> ```python
> import json, logging
> class JSONFormatter(logging.Formatter):
>     def format(self, record):
>         return json.dumps({
>             "time": self.formatTime(record),
>             "level": record.levelname,
>             "component": record.name,
>             "message": record.getMessage(),
>             "topic": getattr(record, "topic", None),
>             "category": getattr(record, "category", None),
>         })
> ```

---

## 14. Schema Registry / Schema Evolution

### 14.1 問題：Payload 格式會變

```
T1：設備發 {"value": 25.3, "unit": "°C"}
T2：工程師加了一個新欄位 {"value": 25.3, "unit": "°C", "tolerance": 0.5}
T3：另一個工程師改了欄位名 {"temp": 25.3, "unit": "°C"}    ← 不相容！

Consumer 在 T3 會爆掉，因為它在找 data.value
```

### 14.2 架構策略：Schema-on-Read + 輕量級 Registry

**不使用重量級 Schema Registry**（如 Confluent Schema Registry / Avro）。
原因：MQTT payload 是 JSON，設備端（PLC/Gateway）產生的格式不受中央控制。

**改用 Schema-on-Read 策略**：
1. `_meta.schema_version` 告訴 Consumer 這個 payload 的格式版本
2. Consumer 根據 version 選擇對應的 parser
3. Schema 定義存在 TimescaleDB 的 `schema_registry` 表中

```
  設備/Gateway                Consumer                   Schema Registry (DB)
  ┌──────────┐              ┌──────────┐               ┌──────────────────┐
  │ publish   │──MQTT──────►│ 讀 _meta  │──查 version──►│ schema_registry  │
  │ payload   │              │ .schema  │               │                  │
  │           │              │ _version │◄── JSON Schema│  topic → version │
  │           │              │          │               │  → json_schema   │
  │           │              │ 驗證     │               │  → changelog     │
  │           │              │ payload  │               │                  │
  └──────────┘              └──────────┘               └──────────────────┘
```

### 14.3 Schema Registry 表設計

```sql
-- 加入 timeseries_schema.sql

-- Schema 版本紀錄
CREATE TABLE IF NOT EXISTS schema_registry (
    schema_id       SERIAL PRIMARY KEY,
    
    -- 哪個 topic pattern 的 schema
    topic_pattern   TEXT NOT NULL,        -- 'TaiwanPrecision/+/+/+/+/Telemetry/Temperature'
    category        TEXT NOT NULL,        -- 'Telemetry'
    
    -- 版本
    schema_version  TEXT NOT NULL,        -- '1.0', '1.1', '2.0'
    
    -- JSON Schema（RFC 8259 / Draft-07）
    json_schema     JSONB NOT NULL,       -- 完整的 JSON Schema 定義
    
    -- 相容性
    is_compatible   BOOLEAN DEFAULT true, -- 是否向後相容（major version 相同 = true）
    breaking_changes TEXT,                -- 不相容時的說明
    
    -- Metadata
    registered_by   TEXT NOT NULL,        -- 誰註冊的
    registered_at   TIMESTAMPTZ DEFAULT NOW(),
    description     TEXT,                 -- 版本說明
    
    UNIQUE(topic_pattern, schema_version)
);

CREATE INDEX IF NOT EXISTS idx_schema_topic ON schema_registry(topic_pattern);
CREATE INDEX IF NOT EXISTS idx_schema_category ON schema_registry(category);
```

### 14.4 版本號規則

遵循語義化版本（Semantic Versioning）：

| 變更類型 | 版本號 | 相容性 | Consumer 影響 |
|---|---|---|---|
| 新增選填欄位 | `1.0` → `1.1` | ✅ 向後相容 | 無影響，忽略未知欄位 |
| 新增必填欄位 | `1.x` → `2.0` | ❌ 不相容 | 需更新 Consumer |
| 欄位改名 | `1.x` → `2.0` | ❌ 不相容 | 需更新 Consumer |
| 欄位刪除 | `1.x` → `2.0` | ❌ 不相容 | 需更新 Consumer |
| 型別改變 | `1.x` → `2.0` | ❌ 不相容 | 需更新 Consumer |

```python
# Consumer 的版本相容性檢查

def is_compatible(payload_version: str, supported_major: int = 1) -> bool:
    """檢查 payload 的 schema_version 是否與 Consumer 相容"""
    major = int(payload_version.split(".")[0])
    return major == supported_major
```

### 14.5 Schema 的生命週期

```
  ┌────────────┐     ┌──────────────┐     ┌──────────────┐
  │ 1. 推斷     │     │ 2. 審核/註冊  │     │ 3. 驗證      │
  │ (自動)      │────►│ (人工)        │────►│ (自動)       │
  │            │     │              │     │              │
  │ Consumer   │     │ Schema Admin │     │ Consumer     │
  │ 首次收到   │     │ 確認 schema  │     │ on_message() │
  │ 新 topic → │     │ 寫入 registry│     │ 驗證每筆     │
  │ genson 推斷│     │ 設定 version │     │ payload      │
  └────────────┘     └──────────────┘     └──────────────┘
```

**Phase 1（目前）：推斷 + 記錄**
- Consumer 首次收到新 topic 時，用 `genson` 推斷 JSON Schema
- 自動寫入 `schema_registry`，version = `1.0`，registered_by = `consumer-auto`
- 不做驗證，只記錄

**Phase 2（成熟期）：驗證 + 拒絕**
- Consumer 收到 payload 時，用 `jsonschema` 驗證是否符合註冊的 schema
- 不符合 → 記錄警告（不丟棄訊息，避免資料遺失）
- 不認識的 schema_version → 寫入新 schema 紀錄 + 通知管理員

**Phase 3（嚴格模式）：強制驗證**
- 不符合 schema 的 payload → 丟棄 + 發送告警
- 只有在 schema 穩定、設備端格式受控時才啟用

### 14.6 Consumer Schema 驗證實作

```python
import jsonschema
from genson import SchemaBuilder

class SchemaValidator:
    """
    輕量級 Schema 驗證器，搭配 schema_registry 表使用。
    """
    
    def __init__(self, db_conn, mode="log"):
        """
        mode:
          "off"    — 不驗證（Phase 0）
          "log"    — 驗證失敗時記 warning，不丟棄（Phase 2）
          "strict" — 驗證失敗時丟棄 + 告警（Phase 3）
        """
        self.db = db_conn
        self.mode = mode
        self.cache: dict[str, dict] = {}   # topic_pattern → json_schema
        self._load_schemas()
    
    def _load_schemas(self):
        """載入所有已註冊的 schema"""
        cur = self.db.cursor()
        cur.execute(
            "SELECT topic_pattern, schema_version, json_schema "
            "FROM schema_registry ORDER BY registered_at DESC"
        )
        for row in cur.fetchall():
            key = f"{row[0]}:{row[1]}"
            self.cache[key] = row[2]
        cur.close()
    
    def validate(self, topic: str, version: str, payload: dict) -> bool:
        """驗證 payload 是否符合註冊的 schema"""
        if self.mode == "off":
            return True
        
        key = f"{topic}:{version}"
        schema = self.cache.get(key)
        
        if schema is None:
            # 未知的 schema → 自動推斷並註冊
            self._auto_register(topic, version, payload)
            return True
        
        try:
            jsonschema.validate(payload, schema)
            return True
        except jsonschema.ValidationError as e:
            if self.mode == "strict":
                logger.error(f"Schema 驗證失敗（丟棄）: {topic} v{version} → {e.message}")
                return False
            else:
                logger.warning(f"Schema 驗證失敗（記錄）: {topic} v{version} → {e.message}")
                return True   # log 模式不丟棄
    
    def _auto_register(self, topic: str, version: str, payload: dict):
        """自動推斷 schema 並寫入 registry"""
        builder = SchemaBuilder()
        builder.add_object(payload)
        inferred = builder.to_schema()
        
        cur = self.db.cursor()
        cur.execute(
            """INSERT INTO schema_registry
               (topic_pattern, category, schema_version, json_schema, registered_by, description)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (topic_pattern, schema_version) DO NOTHING""",
            (topic, "auto", version, json.dumps(inferred),
             "consumer-auto", "自動推斷")
        )
        self.db.commit()
        cur.close()
        self.cache[f"{topic}:{version}"] = inferred
        logger.info(f"自動註冊 schema: {topic} v{version}")
```

### 14.7 Breaking Change 偵測

```python
def detect_breaking_changes(old_schema: dict, new_schema: dict) -> list[str]:
    """
    比較兩個 JSON Schema，找出不相容的變更。
    
    回傳 breaking change 描述列表（空 = 相容）。
    """
    changes = []
    
    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    old_required = set(old_schema.get("required", []))
    new_required = set(new_schema.get("required", []))
    
    # 刪除的欄位
    for prop in old_props:
        if prop not in new_props:
            changes.append(f"欄位 '{prop}' 被刪除")
    
    # 新增的必填欄位
    for prop in new_required - old_required:
        if prop not in old_props:
            changes.append(f"新增必填欄位 '{prop}'")
    
    # 型別改變的欄位
    for prop in old_props:
        if prop in new_props:
            old_type = old_props[prop].get("type")
            new_type = new_props[prop].get("type")
            if old_type != new_type:
                changes.append(f"欄位 '{prop}' 型別從 {old_type} 改為 {new_type}")
    
    return changes
```

---

## 15. 多租戶 / 多廠區架構（概念）

> 此為未來擴展的架構概念，目前不實作。

### 模式一：共享 Broker（適合 < 5 個廠區）

```
所有廠區共享一個 MQTT Broker + TimescaleDB。
用 topic 第 1-2 層做邏輯隔離。

  TaiwanPrecision/Taoyuan/...  ← 桃園廠
  TaiwanPrecision/Hsinchu/...  ← 新竹廠

  ACL 限制：桃園廠的設備不能 subscribe 新竹廠的 topic。
  DB 查詢：asset_path LIKE 'TaiwanPrecision/Taoyuan/%' 天然隔離。
```

- ✅ 管理簡單，一套系統
- ❌ 單點故障，一個 Broker 掛全部掛
- ❌ 跨廠區頻寬需求（如果廠區在不同地理位置）

### 模式二：每廠一套（適合 ≥ 5 個廠區或跨國）

```
每個廠區獨立部署 MQTT Broker + TimescaleDB。
透過 MQTT Bridge 或 Kafka 做跨廠區資料同步。

  ┌─ 桃園廠 ────────────┐          ┌─ 新竹廠 ────────────┐
  │ MQTT Broker (local)  │          │ MQTT Broker (local)  │
  │ TimescaleDB (local)  │          │ TimescaleDB (local)  │
  │ Consumer (local)     │          │ Consumer (local)     │
  └──────────┬───────────┘          └──────────┬───────────┘
             │                                  │
             └──── MQTT Bridge / Kafka ─────────┘
                            │
                  ┌─────────▼──────────┐
                  │  總部 Dashboard     │
                  │  (讀取兩邊的資料)   │
                  └────────────────────┘
```

- ✅ 各廠獨立運作，不受其他廠區影響
- ✅ 各廠區可以有不同的 retention policy
- ❌ 運維成本 × N

### 模式三：混合（推薦）

同一個地理位置的廠區共享 Broker，跨地理位置的獨立部署 + Bridge 同步。

---

## 16. Edge Gateway 離線緩衝 (Store & Forward)（概念）

> 此為 Edge Gateway 層的責任，不在 UNS Core 架構範圍內。
> 但需要確保 UNS 架構能與有 Store & Forward 能力的 Gateway 正確配合。

### 問題

Edge Gateway 到 MQTT Broker 的網路斷線時，設備資料暫時無法上傳。

```
PLC ──► Edge Gateway ──✕── 網路斷線 ──✕──► MQTT Broker
                │
                └─ 資料暫存在 Gateway 本地（SQLite / buffer file）
                   網路恢復後自動重送
```

### 業界常見方案

| Gateway 產品 | Store & Forward 能力 |
|---|---|
| **Kepware KEPServerEX** | ✅ 內建 DataLogger + 斷線重送 |
| **Ignition Edge** | ✅ Store & Forward 是核心功能 |
| **AWS IoT Greengrass** | ✅ 本地 message queue |
| **Azure IoT Edge** | ✅ 離線訊息緩衝 |
| **自建 (Python/Node)** | 需自行用 SQLite 實作 |

### UNS 架構的配合要求

1. **Consumer 的冪等性**：Gateway 重送可能產生重複訊息，Consumer 需要能處理（用 `_meta.timestamp` + `_meta.source` 去重）
2. **時間戳以 Gateway 為準**：`_meta.timestamp` 是 Gateway 採集時的時間，不是送到 Broker 的時間。Consumer 收到延遲資料時，時間戳會是過去的（這是正確的）
3. **不依賴訊息順序**：Store & Forward 重送時，順序可能與原始順序不同。TimescaleDB 的 hypertable 按 `time` 排序，不會受影響

> **結論**：UNS Core 不需要自己實作 Store & Forward。
> 選擇有 Store & Forward 功能的 Edge Gateway 產品，搭配 Consumer 的冪等性設計即可。

---

## 17. Production Context Layer — IoT 資料與生產履歷的關聯

> **這是整個 UNS 架構中最關鍵、也最容易被忽略的一環。**
> 沒有 Production Context，收再多的 time-series data 都是孤兒資料。

### 17.1 問題：兩個世界的認知差距

```
      半導體/光電 CIM 世界                     UNS/IIoT 世界
      (由上而下，MES-Centric)                (由下而上，Data-Centric)

      MES 是核心。                            MQTT Broker 是核心。
      一切以「Lot 在哪裡、做了什麼」為主線。    一切以「設備在傳什麼資料」為主線。

設備資料收集是 MES 指令的副產品：            設備資料收集是目的：
  MES → LotMoveIn                           PLC → 每 5 秒送一筆溫度
  EAP → 下載 Recipe（定義收集哪些 SVID）    「收到就存，存了就有用」???
  設備 → 開始加工、產生 Trace Data
  EAP → 打包 Trace Data（帶 Lot/Recipe）
  MES → LotMoveOut
  所有資料自動掛在 Lot + Step 底下

結果：每筆 trace data 都知道                 結果：一堆 time-series data，
      Lot、Step、Recipe、Product              只知道「設備 X 溫度 25°C」
      → SPC / EDA / FDC 直接可用              → SPC / EDA / FDC 完全無法使用
```

**Walker Reynolds 等 UNS 提倡者**，多來自傳統離散製造（食品飲料、包裝、汽車零件），
熟悉 L0-L2 但對高度自動化的 MES/CIM 架構不了解。
導致 IIoT/UNS 廠商收了 IoT 資料卻不知道要和生產上下文關聯，
**在製程優化與追蹤需求下完全沒辦法用。**

### 17.2 解決方案：Production Context Layer

UNS 需要一個 **Production Context Layer**，把 time-series data 和 MES 的生產上下文關聯：

```
                    ┌─────────────────────────────┐
                    │   Production Context Layer   │
                    │                              │
  MES LotMoveIn ──►│  production_run 表            │
  MES LotMoveOut──►│  (lot + step + recipe +       │
  (via CDC)        │   equipment + time range)     │
                    │              │                │
                    │              ▼                │
  設備 Telemetry ──►│  ts_telemetry                 │
  (via MQTT)       │  + run_id / lot_id / step_id  │
                    │                              │
                    │  → SPC / EDA / FDC 可用的     │
                    │    Trace Data                 │
                    └─────────────────────────────┘
```

### 17.3 `production_run` 表 — 生產上下文 Mapping

**定位**：這不是 MES Lot Table 的複製品。
它是一個 **time-range index**，專門用來把 telemetry 資料和生產上下文關聯。

```
MES Lot Table = Lot 的「目前狀態」（活的、在 Step C）
production_run = 「設備 X 在 T1~T2 加工了 Lot Y」的歷史紀錄
                 → 目的是讓 telemetry data 能用 time range JOIN 找到 lot_id
```

```sql
CREATE TABLE IF NOT EXISTS production_run (
    run_id          SERIAL PRIMARY KEY,

    -- 關聯鍵
    lot_id          TEXT NOT NULL,
    equipment_path  TEXT NOT NULL,         -- 對應 tags.asset_path

    -- 時間範圍（最重要的欄位！做 time-range JOIN 用）
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,           -- NULL = 正在加工

    -- 最少的 context（SPC/EDA 分群用）
    step_id         TEXT NOT NULL,
    pass_number     INTEGER DEFAULT 1,     -- rework 區分
    recipe_id       TEXT,
    product_id      TEXT,

    -- 設備子單元（多腔體設備）
    chamber_id      TEXT,

    -- 擴展（不同客戶不同的欄位放這裡）
    context         JSONB
);
```

| 欄位 | 解決什麼問題 |
|---|---|
| `start_time` / `end_time` | 讓 telemetry JOIN 到 lot：`WHERE t.time BETWEEN r.start_time AND r.end_time` |
| `pass_number` | Rework 時同一 lot + step 會出現多次，用 pass 區分 |
| `chamber_id` | Batch 設備（如爐管）同時加工多片 Lot |
| `context` JSONB | 半導體放 wafer_id/slot，汽車放 VIN，食品放 batch_number |

### 17.4 兩種資料收集模式

UNS 必須同時支援兩種模式（同一工廠可能共存）：

#### 模式 A：持續上傳（Continuous）

```
適用：簡單設備、Sensor、廠務系統
路徑：PLC/Sensor → Edge Gateway → MQTT（固定間隔，無 lot context）
                                      ↓
                                 Consumer 查 production_run
                                 補上 lot_id / step_id
                                      ↓
                                 ts_telemetry (with context)
```

設備不知道目前在加工誰。Consumer 用 equipment_path + 當前時間查 production_run，
找到 `end_time IS NULL` 的那筆（正在加工的 Lot），補上 context 後寫入。

#### 模式 B：指令式收集（Commanded / EAP-style）

```
適用：半導體/光電設備、SECS/GEM 設備
路徑：MES → EAP → 下載 Recipe → 設備開始收集
      設備 → EAP → Trace Data（帶 lot/recipe/SVID）
      EAP → MQTT publish（已帶完整上下文）
                  ↓
             Consumer 直接寫 DB（不需要查 production_run）
```

EAP 就是 MQTT Publisher。它已經知道 lot_id、recipe、step，
payload 直接帶著完整上下文，Consumer 不需要做 enrichment。

#### 兩種模式的 Payload 差異

**模式 A（持續上傳）**：

```json
{
  "_meta": {
    "category": "Telemetry",
    "source": "TaiwanPrecision/Taoyuan/SMT/Line1/Printer",
    "timestamp": "2024-01-15T08:30:00+08:00",
    "collection_mode": "continuous",
    "schema_version": "1.0"
  },
  "data": {
    "value": 25.3,
    "unit": "°C"
  }
}
```

**模式 B（指令式收集 — 加工結束後批次上傳）**：

```json
{
  "_meta": {
    "category": "Telemetry",
    "source": "TaiwanPrecision/Taoyuan/CVD/Line1/Chamber1",
    "timestamp": "2024-01-15T09:30:00+08:00",
    "collection_mode": "commanded",
    "schema_version": "1.0"
  },
  "production_context": {
    "lot_id": "LOT-2024-001",
    "step_id": "CVD-Dep",
    "pass_number": 1,
    "recipe_id": "CVD-SiO2-v3.2",
    "product_id": "Product-A"
  },
  "data": {
    "trace_id": "TRACE-20240115-001",
    "collection_plan": "CP-CVD-Standard",
    "parameters": [
      {
        "svid": "SV001", "name": "ChamberPressure",
        "values": [2.1, 2.1, 2.0, 2.1],
        "unit": "Torr", "interval_ms": 1000
      },
      {
        "svid": "SV002", "name": "RF_Power",
        "values": [500, 502, 501, 500],
        "unit": "W", "interval_ms": 1000
      }
    ],
    "start_time": "2024-01-15T09:25:00+08:00",
    "end_time": "2024-01-15T09:30:00+08:00",
    "total_samples": 300
  }
}
```

### 17.5 UNS 在這個架構中的角色

| 角色 | 是 UNS 的職責？ | 說明 |
|---|---|---|
| 命令設備收集什麼資料 | ❌ **不是** | 這是 MES + EAP + Recipe 的職責 |
| 接收設備/EAP 送來的資料 | ✅ 是 | MQTT Broker 接收 |
| 關聯 telemetry 和 lot context | ✅ 是 | Consumer 做 enrichment 或直接收 EAP 帶好的 context |
| 提供 SPC/EDA/FDC 查詢 | ✅ 是 | Data Access Service 的 gRPC API |
| 管理 Route 定義 | ❌ **不是** | Route 定義在 MES，UNS 只接收 route_id / step_sequence |
| 管理 Lot 狀態 | ❌ **不是** | Lot 狀態在 MES，UNS 只記錄 MoveIn/Out 的時間範圍 |

> **一句話**：UNS 是 CIM 的解耦層 + 資料服務層，不是 CIM 的替代品。
> Production Context 必須是 UNS 的一等公民。

### 17.6 查詢範例：SPC / EDA / FDC

```sql
-- SPC：查某 Product + Step 的製程參數分佈
SELECT t.value, r.lot_id, r.recipe_id
FROM ts_telemetry t
JOIN production_run r ON t.run_id = r.run_id
WHERE r.product_id = 'Product-A'
  AND r.step_id = 'Reflow'
  AND t.tag_id = (SELECT tag_id FROM tags WHERE data_point = 'Temperature')
ORDER BY t.time;

-- EDA：查某 Lot 的完整製程履歷
SELECT r.step_id, r.pass_number, r.recipe_id, r.equipment_path,
       r.start_time, r.end_time,
       tg.data_point, t.time, t.value
FROM production_run r
JOIN ts_telemetry t ON t.run_id = r.run_id
JOIN tags tg ON t.tag_id = tg.tag_id
WHERE r.lot_id = 'LOT-2024-001'
ORDER BY r.start_time, tg.data_point, t.time;

-- FDC：即時監控目前設備上加工中的 Lot 的參數
SELECT t.value, t.time, r.lot_id, r.recipe_id
FROM ts_telemetry t
JOIN production_run r ON t.run_id = r.run_id
WHERE r.equipment_path = 'TaiwanPrecision/Taoyuan/CVD/Line1/Chamber1'
  AND r.end_time IS NULL         -- 目前正在加工
  AND t.time > NOW() - INTERVAL '5 minutes'
ORDER BY t.time DESC;
```

### 17.7 相關檔案

| 檔案 | 說明 |
|---|---|
| `production_context_schema.sql` | production_run 表 + 索引 + 修改 ts_telemetry |
| `production_context_consumer.py` | 雙模式 Consumer（continuous + commanded） |

---

## 18. Measurement Data — 品質量測資料模型

> Telemetry 是製程中的連續數據流（溫度、壓力每秒一筆）。
> **Measurement 是加工完成後的離散量測結果**（厚度、重量、濃度 — 每 Lot 一組）。
> SPC 管制圖的 X-bar / R chart 用的就是 Measurement Data。

### 18.1 為什麼需要獨立的 Measurement Data？

```
Telemetry（製程參數）              Measurement（品質量測）
──────────────────────           ──────────────────────
連續的、高頻的                     離散的、每 Lot/批次一組
加工中產生                         加工後 QC 站量測
反映「設備在做什麼」               反映「產品品質如何」
例：烘箱溫度 180°C                例：藥錠硬度 12.5 N
沒有規格限（Spec Limit）           有 USL/LSL（上下規格限）
不用判定 Pass/Fail                 要判定 Pass/Fail

→ 兩者需要關聯：
  「烘箱溫度 180°C 時做出來的藥錠硬度是 12.5 N」
  這就是 SPC 和製程優化的核心查詢
```

### 18.2 適用產業的 Measurement Data 場景

| 產業 | 量測項目 | 量測頻率 |
|---|---|---|
| **製藥 (Pharma)** | 藥錠硬度、溶出率、水分含量、重量、厚度 | 每批每小時取樣 |
| **精密化學 (Fine Chemical)** | pH 值、濃度、黏度、純度、粒徑 | 每反應批次 |
| **食品飲料 (F&B)** | 糖度（Brix）、pH、含水量、菌落數 | 每批次/每班 |
| **離散製造** | 尺寸（長/寬/高）、重量、表面粗糙度 | 每 N 件抽檢 |
| **SMT/電子** | 錫膏厚度、AOI 缺陷數、ICT 測試值 | 每板/每 Lot |

### 18.3 `ts_measurements` 表設計

```sql
CREATE TABLE IF NOT EXISTS ts_measurements (
    time            TIMESTAMPTZ NOT NULL,
    tag_id          INTEGER NOT NULL REFERENCES tags(tag_id),
    
    -- 量測值
    value           DOUBLE PRECISION NOT NULL,
    
    -- 規格限（SPC 管制用）
    spec_upper      DOUBLE PRECISION,        -- USL（Upper Spec Limit）
    spec_lower      DOUBLE PRECISION,        -- LSL（Lower Spec Limit）
    target_value    DOUBLE PRECISION,        -- 目標值
    
    -- 判定結果
    result          TEXT DEFAULT 'pass',     -- pass / fail / warning / oos (Out of Spec)
    
    -- 生產上下文
    run_id          INTEGER,                 -- 關聯到 production_run
    lot_id          TEXT,
    step_id         TEXT,
    
    -- 取樣資訊
    sample_id       TEXT,                    -- 取樣編號
    sample_position TEXT,                    -- 取樣位置（左/中/右、頭/中/尾）
    inspector       TEXT,                    -- 檢驗員（Pharma 合規需要）
    
    -- 擴展
    context         JSONB                    -- 產業特定欄位
);

SELECT create_hypertable('ts_measurements', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => true
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_meas_lot ON ts_measurements(lot_id, time) WHERE lot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_meas_result ON ts_measurements(result, time) WHERE result != 'pass';
CREATE INDEX IF NOT EXISTS idx_meas_tag_time ON ts_measurements(tag_id, time);
```

### 18.4 Measurement Payload 格式

新增為第 10 種 Category：

```json
{
  "_meta": {
    "category": "Measurement",
    "source": "TaiwanPrecision/Taoyuan/QualityControl/Lab1/Hardness",
    "timestamp": "2024-01-15T10:30:00+08:00",
    "schema_version": "1.0"
  },
  "production_context": {
    "lot_id": "LOT-2024-001",
    "step_id": "HardnessTest",
    "recipe_id": "QC-Hardness-v1.0"
  },
  "data": {
    "measurements": [
      {
        "sample_id": "S001",
        "sample_position": "head",
        "parameter": "Hardness",
        "value": 12.5,
        "unit": "N",
        "spec_upper": 15.0,
        "spec_lower": 10.0,
        "target": 12.0,
        "result": "pass",
        "inspector": "Wang-QC"
      },
      {
        "sample_id": "S002",
        "sample_position": "middle",
        "parameter": "Hardness",
        "value": 11.8,
        "unit": "N",
        "spec_upper": 15.0,
        "spec_lower": 10.0,
        "target": 12.0,
        "result": "pass",
        "inspector": "Wang-QC"
      },
      {
        "sample_id": "S003",
        "sample_position": "tail",
        "parameter": "Hardness",
        "value": 9.2,
        "unit": "N",
        "spec_upper": 15.0,
        "spec_lower": 10.0,
        "target": 12.0,
        "result": "oos",
        "inspector": "Wang-QC"
      }
    ],
    "batch_result": "fail",
    "oos_count": 1,
    "total_samples": 3
  }
}
```

### 18.5 SPC 查詢範例

```sql
-- X-bar chart：查某產品某參數的批次平均值趨勢
SELECT
    r.lot_id,
    r.start_time::DATE AS production_date,
    AVG(m.value) AS x_bar,
    MAX(m.value) - MIN(m.value) AS range_r,
    MIN(m.spec_lower) AS lsl,
    MAX(m.spec_upper) AS usl,
    MIN(m.target_value) AS target
FROM ts_measurements m
JOIN production_run r ON m.run_id = r.run_id
JOIN tags t ON m.tag_id = t.tag_id
WHERE r.product_id = 'Aspirin-500mg'
  AND t.data_point = 'Hardness'
  AND m.time > NOW() - INTERVAL '30 days'
GROUP BY r.lot_id, r.start_time::DATE
ORDER BY r.start_time;

-- OOS（Out of Spec）趨勢：哪些產品的不合格率在上升？
SELECT
    r.product_id,
    DATE_TRUNC('week', m.time) AS week,
    COUNT(*) AS total_measurements,
    COUNT(*) FILTER (WHERE m.result = 'oos') AS oos_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE m.result = 'oos') / COUNT(*), 2) AS oos_rate_pct
FROM ts_measurements m
JOIN production_run r ON m.run_id = r.run_id
WHERE m.time > NOW() - INTERVAL '90 days'
GROUP BY r.product_id, DATE_TRUNC('week', m.time)
ORDER BY r.product_id, week;

-- 製程-品質關聯：當烘箱溫度偏高時，硬度是否偏低？
SELECT
    r.lot_id,
    AVG(tel.value) AS avg_oven_temp,
    AVG(m.value) AS avg_hardness
FROM production_run r
JOIN ts_telemetry tel ON tel.run_id = r.run_id
  AND tel.tag_id = (SELECT tag_id FROM tags WHERE data_point = 'OvenTemperature' LIMIT 1)
JOIN ts_measurements m ON m.run_id = r.run_id
  AND m.tag_id = (SELECT tag_id FROM tags WHERE data_point = 'Hardness' LIMIT 1)
WHERE r.product_id = 'Aspirin-500mg'
  AND r.start_time > NOW() - INTERVAL '90 days'
GROUP BY r.lot_id
ORDER BY avg_oven_temp;
```

---

## 19. Equipment State Model — 設備狀態模型

### 19.1 為什麼需要標準化的設備狀態？

```
目前問題：
  ts_status 的 state_text 是 free text：
    設備 A 傳 "running"
    設備 B 傳 "RUN"
    設備 C 傳 "Producing"
    → 三個都是「生產中」，但字串不同，無法做 OEE 計算
```

### 19.2 狀態模型定義（基於 SEMI E10 簡化版）

SEMI E10 定義了設備利用率的 6 大狀態。我們採用簡化版，適合離散製造/Pharma/F&B：

```
┌───────────────────────────────────────────────────────┐
│                  Equipment States                      │
│                                                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Scheduled Time（排班時間）                       │   │
│  │                                                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌───────────┐  │   │
│  │  │ PRODUCTIVE │  │  STANDBY   │  │   DOWN    │  │   │
│  │  │ 生產中      │  │  待機      │  │  停機     │  │   │
│  │  │            │  │            │  │           │  │   │
│  │  │ ┌────────┐ │  │ ┌────────┐ │  │ ┌───────┐ │  │   │
│  │  │ │Running │ │  │ │Idle    │ │  │ │Planned│ │  │   │
│  │  │ │加工中   │ │  │ │等待投料 │ │  │ │計畫停機│ │  │   │
│  │  │ ├────────┤ │  │ ├────────┤ │  │ ├───────┤ │  │   │
│  │  │ │Loading │ │  │ │Setup   │ │  │ │Repair │ │  │   │
│  │  │ │上下料   │ │  │ │換線/換模│ │  │ │故障維修│ │  │   │
│  │  │ └────────┘ │  │ └────────┘ │  │ └───────┘ │  │   │
│  │  └────────────┘  └────────────┘  └───────────┘  │   │
│  │                                                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                        │
│  ┌─────────────────┐                                    │
│  │ NON_SCHEDULED   │  排班外（週末/假日/非工作時段）       │
│  └─────────────────┘                                    │
└───────────────────────────────────────────────────────┘
```

### 19.3 狀態枚舉定義

```sql
-- 系統核心代碼字典（加入 timeseries_schema.sql 或獨立執行）

CREATE TABLE IF NOT EXISTS master_data_codes (
    category        TEXT NOT NULL,
    code_value      TEXT NOT NULL,    -- 標準名稱 (e.g. PRD, SBY)
    label           TEXT NOT NULL,    -- Productive / Standby / Down 可讀名稱
    metadata        JSONB,            -- oee_bucket, color 等額外資訊
    description     TEXT,
    PRIMARY KEY (category, code_value)
);

INSERT INTO master_data_codes (category, code_value, label, metadata, description) VALUES
    ('equipment_state', 'PRD', 'Productive', '{"oee_bucket": "availability", "color": "#4CAF50"}', '正常加工中'),
    ('equipment_state', 'SBY', 'Standby', '{"oee_bucket": "availability", "color": "#FFC107"}', '待機中/換線'),
    ('equipment_state', 'ENG', 'Engineering', '{"oee_bucket": "excluded", "color": "#7E57C2"}', '工程測試/校正'),
    ('equipment_state', 'UDT', 'Unscheduled Downtime', '{"oee_bucket": "availability", "color": "#F44336"}', '非計畫停機（故障/警報）'),
    ('equipment_state', 'SDT', 'Scheduled Downtime', '{"oee_bucket": "availability", "color": "#2196F3"}', '計畫保養'),
    ('equipment_state', 'NSC', 'Non-Scheduled', '{"oee_bucket": "excluded", "color": "#9E9E9E"}', '非排班時間')
ON CONFLICT (category, code_value) DO NOTHING;
```

### 19.4 Data Engine 與 Master Data 的邊界 (ADR-005)

**決策**：UNS Platform 的 Data Engine **絕對不負責**在資料攝取 (Ingestion) 過程中查詢 `master_data_codes` 進行代碼翻譯 (e.g. 將 `100` 翻譯成 `PRD`)。

**背景與考量**：
1. **效能瓶頸**：如果在每秒上萬筆的 Ingestion Pipeline 中加入 N+1 關聯式資料庫 Lookup，會劇烈拖垮 Data Engine 的吞吐量。
2. **架構脆弱性**：若查無代碼，Data Engine 無法輕易決定是該丟棄此筆資料、存入 NULL、還是觸發警報，這將導致資料遺失或維運噩夢。
3. **單一資料源 (SSOT) 衝突**：UNS 是 Data Hub，真正的 Master Data (如報警碼、設備狀態碼) 應該由 MES / CMMS / EAP 定義與維護。

**實作規範**：
*   **聰明的邊緣，笨的管線 (Smart Edge, Dumb Pipe)**：代碼值的轉換與標準化 (Mapping) 必須發生在寫入 MQTT 之前（即 Edge Gateway 或 EAP 中）。進入 MQTT 的 Payload 必須已經是符合 Schema 契約的標準代碼 (如 `PRD`, `SBY`)。
*   **例外處理 (保留原始碼)**：若客戶要求保留機台原始代碼以利稽核，Schema 設計應利用多欄位（如 `{"state": "PRD", "raw_state_code": "100"}`）將兩者平鋪傳入，Data Engine 僅負責無腦寫入，不負責驗證兩者關聯。
*   **Dict 的真實用途**：`master_data_codes` 定位為 **「讀取優化的字典 (Read-Only Dictionary)」**。它專供 OEE 分析引擎 (如計算 `oee_bucket`)、前端 Dashboard (解析 `color` 與 `label`)，或 API 消費者在「讀取時」 JOIN 使用。

---

### 19.5 修改 `ts_status` 表

```sql
-- 加上標準化的 state 索引
CREATE INDEX IF NOT EXISTS idx_status_state
    ON ts_status(tag_id, state, time);
```

### 19.5 Status Payload 格式更新

```json
{
  "_meta": {
    "category": "Status",
    "source": "TaiwanPrecision/Taoyuan/Packaging/Line1/Bagger",
    "timestamp": "2024-01-15T08:00:00+08:00",
    "schema_version": "1.0"
  },
  "data": {
    "state_text": "setup_changeover",
    "state_code": 201,
    "previous_state": "running",
    "previous_state_code": 100,
    "reason": "產品切換：Aspirin-500mg → Ibuprofen-200mg",
    "operator": "Chen-OP"
  }
}
```

### 19.6 OEE 計算基礎

OEE = Availability × Performance × Quality

```sql
-- ═══ OEE 計算 View ═══

CREATE OR REPLACE VIEW equipment_oee AS
WITH state_durations AS (
    -- 計算每個設備、每天的各狀態持續時間
    SELECT
        s.tag_id,
        DATE_TRUNC('day', s.time) AS day,
        e.label AS state_category,
        e.metadata->>'oee_bucket' AS oee_bucket,
        -- 每筆狀態持續到下一筆為止
        EXTRACT(EPOCH FROM (
            LEAD(s.time) OVER (PARTITION BY s.tag_id ORDER BY s.time)
            - s.time
        )) AS duration_seconds
    FROM ts_status s
    JOIN master_data_codes e ON s.state = e.code_value AND e.category = 'equipment_state'
    WHERE s.state IS NOT NULL
),
daily_summary AS (
    SELECT
        tag_id,
        day,
        -- 排班時間 = 全部時間 - non_scheduled
        SUM(duration_seconds) FILTER (WHERE oee_bucket = 'availability') AS scheduled_seconds,
        -- 生產時間 = productive
        SUM(duration_seconds) FILTER (WHERE state_category = 'Productive') AS productive_seconds,
        -- 停機時間 = down + standby
        SUM(duration_seconds) FILTER (WHERE state_category LIKE '%Downtime%') AS down_seconds,
        SUM(duration_seconds) FILTER (WHERE state_category = 'Standby') AS standby_seconds
    FROM state_durations
    WHERE (oee_bucket IS NULL OR oee_bucket != 'excluded')
    GROUP BY tag_id, day
)
SELECT
    t.asset_path,
    t.display_name,
    ds.day,
    ds.scheduled_seconds,
    ds.productive_seconds,
    ds.down_seconds,
    ds.standby_seconds,
    -- Availability = productive / scheduled
    ROUND(100.0 * ds.productive_seconds / NULLIF(ds.scheduled_seconds, 0), 1) AS availability_pct
FROM daily_summary ds
JOIN tags t ON ds.tag_id = t.tag_id
ORDER BY t.asset_path, ds.day;

-- 注意：完整 OEE 需要 Performance（實際產量/理論產量）和 Quality（合格品/總產量）。
-- Performance 來自 ts_metrics 的產量計數器。
-- Quality 來自 ts_measurements 的合格率。
-- Availability 來自此 View。
```

```sql
-- ═══ 完整 OEE 查詢（結合 3 個資料來源）═══

-- 查某設備某天的 OEE
SELECT
    oee.asset_path,
    oee.day,
    oee.availability_pct,
    -- Performance（假設有產量 metrics）
    ROUND(100.0 * met.actual_output / NULLIF(met.theoretical_output, 0), 1)
        AS performance_pct,
    -- Quality（假設有量測合格率）
    ROUND(100.0 * meas.pass_count / NULLIF(meas.total_count, 0), 1)
        AS quality_pct,
    -- OEE = A × P × Q
    ROUND(
        (oee.availability_pct / 100.0)
        * (100.0 * met.actual_output / NULLIF(met.theoretical_output, 0) / 100.0)
        * (100.0 * meas.pass_count / NULLIF(meas.total_count, 0) / 100.0)
        * 100, 1
    ) AS oee_pct
FROM equipment_oee oee
LEFT JOIN (
    -- Performance 資料（from ts_metrics）
    SELECT tag_id, DATE_TRUNC('day', time) AS day,
           SUM((data->>'actual_output')::float) AS actual_output,
           SUM((data->>'theoretical_output')::float) AS theoretical_output
    FROM ts_metrics
    GROUP BY tag_id, DATE_TRUNC('day', time)
) met ON met.tag_id = (
    SELECT tag_id FROM tags WHERE asset_path = oee.asset_path AND category = 'Metrics' LIMIT 1
) AND met.day = oee.day
LEFT JOIN (
    -- Quality 資料（from ts_measurements）
    SELECT run_id, lot_id,
           COUNT(*) AS total_count,
           COUNT(*) FILTER (WHERE result = 'pass') AS pass_count
    FROM ts_measurements
    GROUP BY run_id, lot_id
) meas ON TRUE  -- 較簡化的 JOIN，實務需更精確
WHERE oee.day = '2024-01-15';
```

### 19.7 狀態轉移規則

```python
# 合法的狀態轉移（用於 Consumer 驗證）
VALID_TRANSITIONS = {
    "running":            {"loading_unloading", "idle", "setup_changeover", "unplanned_down", "planned_maintenance"},
    "loading_unloading":  {"running", "idle"},
    "idle":               {"running", "setup_changeover", "warmup", "planned_maintenance", "non_scheduled"},
    "setup_changeover":   {"warmup", "running", "idle"},
    "warmup":             {"running", "unplanned_down"},
    "waiting_material":   {"running", "idle"},
    "waiting_operator":   {"running", "idle"},
    "planned_maintenance":{"idle", "warmup", "calibration"},
    "unplanned_down":     {"repair"},
    "repair":             {"idle", "warmup", "calibration"},
    "calibration":        {"idle", "warmup"},
    "non_scheduled":      {"idle", "planned_maintenance"},
    "holiday":            {"idle"},
    "engineering":        {"idle", "running"},
}

def validate_transition(current: str, next_state: str) -> bool:
    """檢查狀態轉移是否合法"""
    allowed = VALID_TRANSITIONS.get(current, set())
    return next_state in allowed
```

---

## 20. 高可用性 (HA) 策略

### 20.1 各元件的故障影響

| 元件 | 故障影響 | 可接受停機時間 |
|---|---|---|
| MQTT Broker | 設備無法送資料，即時監控全停 | < 1 分鐘 |
| Consumer | 資料不再寫入 DB，但 Broker 有緩衝（QoS 1） | < 5 分鐘 |
| TimescaleDB | 所有查詢停止，Consumer INSERT 失敗 | < 5 分鐘 |
| CDC Transform | MES 事件不再同步到 UNS | < 10 分鐘 |
| Grafana/Prometheus | 監控看不到，但資料不受影響 | < 30 分鐘 |

### 20.2 HA 架構

```
                    ┌─── VIP / Load Balancer ───┐
                    │                            │
              ┌─────▼─────┐              ┌───────▼───────┐
              │ MQTT Broker│              │ MQTT Broker   │
              │ (Primary)  │◄── Bridge ──►│ (Standby)     │
              └─────┬──────┘              └───────────────┘
                    │
         ┌──────────┼──────────┐
         ▼          ▼          ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │Consumer-1│ │Consumer-2│ │Consumer-3│    ← Multi-instance
   │(Topic A) │ │(Topic B) │ │(Topic C) │       by topic partition
   └────┬─────┘ └────┬─────┘ └────┬─────┘
        │            │            │
        └────────────┼────────────┘
                     ▼
              ┌──────────────┐
              │ TimescaleDB  │
              │  (Primary)   │
              │      │       │
              │      ▼       │
              │  (Replica)   │     ← Streaming Replication
              └──────────────┘
```

### 20.3 各元件 HA 方案

#### MQTT Broker

| 方案 | 複雜度 | 說明 |
|---|---|---|
| **EMQX Cluster** | ⭐⭐⭐ | 內建 clustering，自動 failover。推薦 |
| **Mosquitto + Bridge** | ⭐⭐ | 兩台 Mosquitto 用 bridge 同步，手動 failover |
| **HiveMQ** | ⭐⭐⭐ | 商用，自動 clustering + load balance |
| **VerneMQ** | ⭐⭐⭐ | 開源，Erlang-based clustering |

> **推薦**：小規模用 Mosquitto Bridge（夠用），中大規模換 EMQX。

#### Consumer

```python
# Consumer multi-instance by topic partition

# Consumer-1 訂閱 A 廠區
CONSUMER_1_TOPICS = "TaiwanPrecision/Taoyuan/SMT/#"

# Consumer-2 訂閱 B 廠區
CONSUMER_2_TOPICS = "TaiwanPrecision/Taoyuan/Assembly/#"

# Consumer-3 訂閱 C 廠區
CONSUMER_3_TOPICS = "TaiwanPrecision/Taoyuan/QualityControl/#"

# 每個 Consumer instance 是獨立 process
# 任一掛掉不影響其他，可用 systemd / Docker restart 自動重啟
```

#### TimescaleDB

```
Primary-Replica 架構：
  - Primary: 處理所有 INSERT（Consumer 寫入）
  - Replica: 處理 SELECT（Dashboard / SPC / EDA 查詢）
  - Streaming Replication: 非同步，lag < 1 秒

  Consumer → Primary (INSERT)
  Dashboard → Replica (SELECT)     ← 讀寫分離
  SPC/EDA → Replica (SELECT)

  Primary 故障時：promote Replica, Consumer 改連新 Primary
```

### 20.4 故障恢復 Runbook（簡表）

| 故障情境 | 恢復步驟 | 預計恢復時間 |
|---|---|---|
| Consumer crash | Docker auto-restart 或 systemd restart | < 30 秒 |
| Consumer 與 DB 斷線 | Consumer 自動重連（已內建 retry） | < 1 分鐘 |
| MQTT Broker 重啟 | Client 自動重連（QoS 1 訊息由 Broker 保留） | < 1 分鐘 |
| TimescaleDB Primary 故障 | promote Replica → 更新 Consumer 連線字串 | < 5 分鐘 |
| 整機故障 | 從 Backup 恢復 DB + 重啟所有服務 | < 30 分鐘 |

---

## 21. 效能基準與容量規劃

### 21.1 容量估算模型

```
每台設備的資料產生量（典型值）：

  Telemetry：  10 個參數 × 每 5 秒一筆 = 120 筆/分鐘
  Status：     狀態變更時才送 ≈ 5 筆/小時
  Alarm：      異常時才送 ≈ 2 筆/小時
  Measurement：每批次 10 筆（QC 站）

  → 每台設備約 120 筆/分鐘 ≈ 7,200 筆/小時
```

| 工廠規模 | 設備數 | 每秒寫入 | 每日資料量 | 年資料量 |
|---|---|---|---|---|
| **小型**（1 條線） | 10 台 | ~20 筆/秒 | ~170 萬筆 | ~3 GB |
| **中型**（5 條線） | 50 台 | ~100 筆/秒 | ~860 萬筆 | ~15 GB |
| **大型**（20 條線） | 200 台 | ~400 筆/秒 | ~3,450 萬筆 | ~60 GB |
| **超大型**（多廠區） | 1000 台 | ~2,000 筆/秒 | ~1.7 億筆 | ~300 GB |

### 21.2 各元件的效能瓶頸

```
                        瓶頸分析

  MQTT Broker ─────── 10,000+ msg/sec ────── 通常不是瓶頸
       │
  Consumer     ─────── 瓶頸在這裡 ──────── 逐筆 INSERT 約 500~1K 筆/秒
       │                                    batch INSERT 可達 5K~10K 筆/秒
       ▼
  TimescaleDB  ─────── batch INSERT 約 50K~100K 筆/秒 ── 不是瓶頸
                        查詢端：看索引設計和查詢複雜度
```

### 21.3 效能優化建議

| 優化項 | 做法 | 預期效果 |
|---|---|---|
| **Consumer batch INSERT** | 累積 100~500 筆後一次 `execute_values()` | 5~10 倍吞吐量提升 |
| **Consumer 多 instance** | 按 topic / 廠區分流，各跑一個 process | 線性水平擴展 |
| **TimescaleDB chunk 調整** | `chunk_time_interval` 根據資料量調整 | 查詢效能 |
| **連線池** | Consumer 用 `psycopg2.pool` 而非逐次建連 | 減少連線開銷 |
| **壓縮** | `ALTER TABLE ... SET (timescaledb.compress)` | 儲存空間減 90% |

```sql
-- TimescaleDB 壓縮設定
ALTER TABLE ts_telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tag_id',
    timescaledb.compress_orderby = 'time DESC'
);

-- 30 天以上的 chunk 自動壓縮
SELECT add_compression_policy('ts_telemetry', INTERVAL '30 days');
```

### 21.4 建議的硬體規格

| 規模 | CPU | RAM | 磁碟 | 備註 |
|---|---|---|---|---|
| **小型** (10 設備) | 4 cores | 8 GB | 100 GB SSD | 單機可搞定 |
| **中型** (50 設備) | 8 cores | 32 GB | 500 GB SSD | DB 和 Consumer 分開 |
| **大型** (200 設備) | 16 cores | 64 GB | 2 TB NVMe | DB Primary-Replica |
| **超大型** (1000+) | 32+ cores | 128+ GB | 4+ TB NVMe | 多 Consumer + DB cluster |
