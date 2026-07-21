# UNS Namespace Data Platform — Product Vision

## 一句話定位

> **工廠資料的 Single Source of Truth**
> 收 → 存 → 查 → 管，一個平台搞定。Namespace 改了，資料不斷。

---

## 產品定位

| | HighByte（DataOps）| 我們（Data Platform）|
|---|---|---|
| 角色 | 水管（資料搬運） | 水塔（資料的家） |
| 資料存在哪 | 別人的 DB | 我們的 DB |
| 客戶能不能離開 | 容易（中間件可替換）| 困難（歷史資料都在這裡）|
| 護城河 | 弱 | **強：資料黏性 + 整合生態** |

---

## 系統架構

```
  ┌─ 資料來源 ───────────────────────────────────┐
  │  PLC / Sensor (MQTT)                         │
  │  EAP / Gateway (MQTT)                        │
  │  MES / ERP (REST API)                        │
  │  CSV / File Upload                           │
  └──────┬───────────────────────────────────────┘
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │         UNS Data Platform                    │
  │                                              │
  │  ┌────────────────────────────────────────┐  │
  │  │    Namespace Manager (Web UI)          │  │
  │  │    拖拉式定義 / Tag 管理 / ACL 設定     │  │
  │  │    Per-topic persistence config        │  │
  │  └────────────────────┬───────────────────┘  │
  │                       │                      │
  │  ┌────────────────────▼───────────────────┐  │
  │  │         Integration Layer              │  │
  │  │                                        │  │
  │  │  MQTT Broker ◄─── EMQX (embedded)     │  │
  │  │  REST API    ◄─── FastAPI             │  │
  │  │  gRPC API    ◄─── 歷史查詢服務         │  │
  │  └────────────────────┬───────────────────┘  │
  │                       │                      │
  │  ┌────────────────────▼───────────────────┐  │
  │  │         Data Engine                    │  │
  │  │                                        │  │
  │  │  Consumer     : MQTT → DB 寫入         │  │
  │  │  Tag Registry : tag_id 身份管理        │  │
  │  │  Enrichment   : Production Context     │  │
  │  │  Migration    : namespace 變更自動遷移  │  │
  │  └────────────────────┬───────────────────┘  │
  │                       │                      │
  │  ┌────────────────────▼───────────────────┐  │
  │  │         TimescaleDB                    │  │
  │  │  tags + tag_source_mapping             │  │
  │  │  ts_telemetry / ts_status / ts_alarms  │  │
  │  │  ts_measurements / production_run      │  │
  │  └────────────────────────────────────────┘  │
  └──────────────────────────────────────────────┘
         │
         ▼
  ┌─ 資料消費者 ─────────────────────────────────┐
  │  Dashboard (Grafana / 自建)                  │
  │  SPC / EDA 系統                              │
  │  MES / ERP                                   │
  │  AI / ML Pipeline                            │
  └──────────────────────────────────────────────┘
```

---

## 四大核心能力

### 1. Namespace Management（管理）

管理者在 Web UI 上定義工廠的 ISA-95 階層：

```
拖拉式操作：
  ✅ 建立 / 移動 / 重新命名 namespace node
  ✅ 在每個 node 底下定義 Tag（名稱、資料型態、單位）
  ✅ 設定每個 node 的 ACL（誰可 publish、誰可 subscribe）
  ✅ 設定每個 Tag 的持久化策略（存/不存/retention 天數）

關鍵設計：
  - Node 移動 → tag_source_mapping 自動更新 → 歷史資料不中斷
  - ACL 變更 → 自動同步到 EMQX（透過 EMQX REST API）
  - 異動紀錄 → 所有 namespace 變更都有 audit log
```

### 2. Data Persistence（存）

```
Per-Topic 持久化設定（管理者在 UI 上對每個 topic 設定）：

  模式 A：Persist to DB（寫入 TimescaleDB）
    - 指定 retention 天數
    - 指定 chunk interval
    - 自動壓縮策略

  模式 B：Retained Message Only（最新值快取）
    - MQTT retained message
    - 不寫 DB（節省儲存）
    - 適合：設備狀態、heartbeat

  模式 C：Pass-through（純轉發）
    - 不存、不 retain
    - 純 event / command
```

### 3. Data Access（查）

```
三種拿資料的方式：

  即時：MQTT Subscribe
    - Consumer 訂閱 topic wildcard，拿 real-time 資料

  歷史：gRPC Query API
    - BrowseAssets() → 瀏覽 namespace 樹
    - ListTags() → 某 node 底下有哪些 tag
    - QueryTelemetry(tag_ids, time_range) → 歷史數值
    - QueryMeasurements(product, parameter) → SPC 用

  整合：REST API
    - GET /api/v1/tags/{asset_path}/values
    - POST /api/v1/tags/{asset_path}/values（外部寫入）
    - GET /api/v1/namespace/tree（取得完整 namespace 結構）
```

### 4. ACL & Security（管控）

```
分層存取控制：

  Namespace 層級：
    - 哪些 MQTT user 可以 publish 到這個 node（及子 node）
    - 哪些 MQTT user 可以 subscribe
    - 自動生成 EMQX ACL 規則

  API 層級：
    - gRPC / REST 的 RBAC（operator / engineer / admin / readonly）
    - JWT 或 API Key 認證

  DB 層級：
    - 已有的 PostgreSQL 角色分離
```

---

## 三大差異化（vs 所有競品）

### 🔥 1. Tag 身份分離 + Live Migration

```
目前做到這件事的產品：0

場景：工廠把 Line1 的印刷機搬到 Line2
  - 所有競品：歷史資料斷裂，需要人工重新 mapping
  - 我們：管理者在 UI 拖拉 node → 自動更新 mapping → 歷史資料連續不中斷

底層機制：
  tag_id 永遠不變
  tag_source_mapping 表負責 MQTT topic ↔ tag_id 的對應
  Namespace 變更只更新 mapping，不動資料
```

### 🔥 2. Per-Topic Persistence Config

```
目前做到這件事的產品：0

管理者可以精細控制：
  「這個溫度 tag 要存 90 天」
  「這個 heartbeat 只要 retained，不用存」
  「這個 alarm 要存 1 年」

不是全存或全不存，而是每個 topic 獨立設定。
```

### 🔥 3. Production Context Layer

```
目前做到這件事的產品：0

IoT 資料自動關聯到 Lot / Step / Recipe
讓 SPC / EDA / OEE 直接可用
不是「收了一堆孤兒溫度資料」，而是「知道這個溫度是在做哪個批次」
```

---

## 目標市場

### 市場選擇原則

> **好的生意 = 好的產品 × 深刻的產業理解 × 信任關係**
> 選「我們最有 domain knowledge 的產業」，不是選「市場規模最大的」。

### 🥇 首選：製藥 CDMO + 精密化學

| 產業 | 痛點 | 我們的價值 | 驅動力 |
|---|---|---|---|
| **製藥 CDMO** | FDA 合規、紙本、MES 剛起步 | Audit + 批次追溯 + Production Context | 法規（不得不做）|
| **精密化學** | 批次參數追蹤、製程最佳化 | Historian + SPC + 參數關聯分析 | 良率/成本 |

### 🥈 次選：F&B + EMS/SMT

| 產業 | 痛點 | 我們的價值 | 注意 |
|---|---|---|---|
| **食品飲料** | OEE 低（53-65%）、多產線 | OEE 看板 + 設備狀態 | 客單價低 |
| **電子代工** | 多設備、品質追溯 | SPC + 品質追溯 | 大廠已有系統 |

### ❌ 明確排除

半導體（成熟方案）、汽車 OEM（競爭太激烈）、水務（無 domain knowledge）

---

## 產品 Roadmap

> 最後對齊實際進度：2026-07-21（開發於 2026-03-17 中斷約 4 個月後重新盤點，
> 逐項對照 PROGRESS.md 與程式碼實際狀態校正，而非只看 commit 訊息宣稱）。

### Phase 1：PoC（核心驗證）— ✅ 全數完成

```
範圍：
  ✅ Namespace Tree 視覺化 + 拖拉編輯（Web UI）
  ✅ Tag 管理（CRUD + metadata）
  ✅ EMQX 整合（Broker）
  ✅ TimescaleDB 寫入（Consumer）
  ✅ 基本歷史查詢（REST API）
  ✅ Per-topic persistence config
  ✅ Tag 身份分離 + Migration 驗證

目標：展示核心差異化，可以 demo 給客戶看 — 已達成
```

### Phase 2：MVP — 大部分完成，1 項未動 + 1 項未完工

```
新增：
  ◻ ACL 管理 UI + EMQX 同步            — 未開始（PoC 階段 Mock Auth 決策延後，見下方 ADR）
  🔨 gRPC 查詢 API（語義資料層 ADR-005） — 部分完成：GetSnapshot/PublishData/SearchNamespace(gRPC) 已完成，
                                          QueryHistory 仍是 placeholder，SearchNamespace REST 入口未接 attributes，
                                          semantic E2E test 未納入 CI（重啟開發後第一優先項目）
  ✅ Production Context Layer          — 完成（自動附加 run_id/lot_id）
  ✅ Measurement 寫入 + SPC 查詢        — 完成（Data Category 路由含 measurement 類別）
  ✅ Equipment State + OEE 計算         — 完成（ts_status + Synchronized RCA Timeline + oee_tool.py）
  ◻ Retention Policy 自動執行           — 未完成：`PUT /api/v1/system/retention` 仍回 501 stub

目標：可以在 pilot 客戶部署的最小產品 — 尚未達成，卡在語義層收尾與 ACL/Retention 兩項未動工的功能
```

### Phase 3：Production

```
新增：
  ◻ HA（EMQX cluster + DB replica）
  ◻ Multi-site 支援
  ◻ Audit Log + 合規報表
  ◻ Grafana 整合（出廠 dashboard）
  ✅ Docker Compose 一鍵部署            — 提前達成（docker-compose.yml + ops/start_all.sh）
  ◻ 文件 + 教學影片

目標：可賣給客戶的完整產品
```
