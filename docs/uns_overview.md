# UNS (Unified Namespace) 架構知識庫

> 完整的 UNS 設計文件、資料庫 schema、Consumer 模組、運維工具。
> 涵蓋 ISA-95 L0–L4 全層級的資料交換策略。

## 架構概覽

```
 L4  ERP ──gRPC──┐                        ┌── SPC Tool
 L3  MES ──CDC───┤                        ├── OEE Tool
                 ▼                        │
          ┌──────────────────────────────┐ │
          │           UNS               │ │
          │                             │ │
          │  MQTT Broker (設備資料)      │ │
          │  gRPC Service (交易/查詢)    │ │
          │  Consumer (寫入/enrichment)  │ │
          │  TimescaleDB (持久化)        │ ◄── Data Access
          │  Production Context Layer   │ │
          │  Monitoring Stack           │ │
          └──────────────────────────────┘ │
                 ▲                        │
 L2  SCADA ─────┤                        ├── Grafana
 L1  PLC ───────┤                        └── EDA
 L0  Sensor ────┘
```

## 檔案清單

### 設計文件

| 檔案 | 內容 |
|---|---|
| `uns_architecture_decisions.md` | 架構設計決策紀錄（21 章，2100+ 行） |
| `payload_standard_spec.md` | 10 種 Category 的 Payload 標準規格 |
| `topic_naming_guide.md` | MQTT Topic 命名規範 |
| `namespace_template.yaml` | ISA-95 Topic Tree 模板 |

### 資料庫 Schema

| 檔案 | 內容 |
|---|---|
| `timeseries_schema.sql` | Tags + 5 張 ts_* 表（核心 schema） |
| `production_context_schema.sql` | production_run + ts_* 欄位擴展 |
| `measurement_and_state_schema.sql` | ts_measurements + equipment_state_def + OEE View |

### Consumer 模組

| 檔案 | 內容 |
|---|---|
| `consumer_example.py` | 基礎 MQTT Consumer + TagAdmin |
| `production_context_consumer.py` | 雙模式 Consumer（Continuous + Commanded/EAP） |
| `measurement_consumer.py` | Measurement 處理（Spec Limit 判定 + Cpk） |
| `equipment_state_consumer.py` | 設備狀態標準化（E10 mapping + 轉移驗證） |

### CDC

| 檔案 | 內容 |
|---|---|
| `cdc_mes_bridge/` | Debezium CDC 範例（MES DB → UNS） |

### 運維工具 (ops/)

| 檔案 | 內容 |
|---|---|
| `ops/retention_policy.yaml` | 資料保留策略設定 |
| `ops/apply_retention.py` | 自動套用 retention → TimescaleDB |
| `ops/archive_to_cold_storage.py` | 超期資料歸檔到 S3/NAS |
| `ops/setup_db_security.sql` | DB 角色 + 權限設定 |
| `ops/mosquitto/` | MQTT Broker 設定（TLS + ACL） |
| `ops/monitoring/` | Prometheus + Grafana + Consumer Metrics |
| `ops/schema_registry.sql` | Schema Registry 表 DDL |
| `ops/schema_validator.py` | Schema 驗證器（off/log/strict） |
| `ops/spc_tool.py` | SPC 分析 CLI（Cpk / X-bar / OOS / 關聯） |
| `ops/oee_tool.py` | OEE 分析 CLI（稼動率 / 排名 / 停機 Pareto） |

## 部署順序

```bash
# 1. 建立 DB
psql -U postgres -f timeseries_schema.sql
psql -U postgres -f production_context_schema.sql
psql -U postgres -f measurement_and_state_schema.sql
psql -U postgres -f ops/schema_registry.sql
psql -U postgres -f ops/setup_db_security.sql

# 2. 設定 retention + 歸檔
python ops/apply_retention.py --config ops/retention_policy.yaml --dry-run

# 3. 設定 MQTT Broker
cp ops/mosquitto/* /etc/mosquitto/

# 4. 啟動監控
cd ops/monitoring && docker compose up -d

# 5. 啟動 Consumer
python consumer_example.py
```

## 分析工具

```bash
# SPC：查 Cpk
python ops/spc_tool.py cpk --parameter Hardness --product Aspirin-500mg

# SPC：X-bar chart
python ops/spc_tool.py xbar --parameter Hardness --days 30

# SPC：OOS 趨勢
python ops/spc_tool.py oos --days 90

# SPC：製程-品質關聯
python ops/spc_tool.py correlation --product Aspirin-500mg \
    --process-param OvenTemperature --quality-param Hardness

# OEE：單一設備
python ops/oee_tool.py oee --equipment "TaiwanPrecision/.../Printer" --days 7

# OEE：全廠排名
python ops/oee_tool.py ranking --days 7

# OEE：停機 Pareto
python ops/oee_tool.py downtime --days 30

# OEE：即時狀態
python ops/oee_tool.py status
```
