# UNS 運維工具 (ops/)

部署和維運 UNS 系統的設定檔和腳本。

## 檔案清單

### 資料保留 & 歸檔

| 檔案 | 用途 | 何時使用 |
|---|---|---|
| `retention_policy.yaml` | 資料保留策略設定 | 部署前修改保留天數 |
| `apply_retention.py` | 自動套用 retention → TimescaleDB | 部署時 + 更新策略時 |
| `archive_to_cold_storage.py` | 超期資料歸檔到 S3/NAS | 每月排程執行 |

### 安全性

| 檔案 | 用途 | 何時使用 |
|---|---|---|
| `setup_db_security.sql` | DB 角色 + 權限設定 | 部署時執行一次 |
| `mosquitto/acl.conf` | MQTT 設備級存取控制 | 新增設備時更新 |
| `mosquitto/mosquitto.conf` | MQTT Broker TLS 設定 | 部署時複製到 /etc/mosquitto/ |

### 監控 (monitoring/)

| 檔案 | 用途 | 何時使用 |
|---|---|---|
| `monitoring/docker-compose.yml` | Prometheus + Grafana 一鍵啟動 | 部署時 `docker compose up -d` |
| `monitoring/prometheus.yml` | Prometheus scrape 設定 | 修改監控目標時 |
| `monitoring/prometheus-alerts.yml` | 17 條告警規則（4 元件） | 調整告警閾值時 |
| `monitoring/consumer_metrics.py` | Consumer 可 import 的 metrics 模組 | Consumer 開發時 |

### Schema Registry

| 檔案 | 用途 | 何時使用 |
|---|---|---|
| `schema_registry.sql` | schema_registry 表 DDL | 部署時執行一次 |
| `schema_validator.py` | Schema 驗證器（off/log/strict） | Consumer 開發時 import |

## 部署順序

```bash
# 1. 建立 TimescaleDB schema + Schema Registry
psql -U postgres -d uns_timeseries -f ../timeseries_schema.sql
psql -U postgres -d uns_timeseries -f schema_registry.sql

# 2. 設定 DB 安全性（角色 + 權限）
#    ⚠ 請先修改 setup_db_security.sql 中的密碼！
psql -U postgres -d uns_timeseries -f setup_db_security.sql

# 3. 套用 retention policy + continuous aggregates
python apply_retention.py \
    --config retention_policy.yaml \
    --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries \
    --dry-run

python apply_retention.py \
    --config retention_policy.yaml \
    --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries

# 4. 設定 MQTT Broker（見 mosquitto/ 目錄）

# 5. 啟動監控
cd monitoring && docker compose up -d

# 6. 設定歸檔排程
# crontab -e
# 0 2 1 * * python /path/to/archive_to_cold_storage.py \
#     --config /path/to/retention_policy.yaml \
#     --db-url postgresql://uns_admin:password@localhost:5432/uns_timeseries
```

## Consumer 整合範例

```python
# 在 consumer_example.py 中整合 metrics + schema 驗證

from ops.monitoring.consumer_metrics import metrics
from ops.schema_validator import SchemaValidator

# 啟動
metrics.start(consumer_id="consumer-01")
validator = SchemaValidator(db_conn, mode="log", metrics=metrics)

# on_message callback
def on_message(client, topic, payload, qos, properties):
    msg = json.loads(payload)
    meta = msg.get("_meta", {})
    version = meta.get("schema_version", "1.0")

    if not validator.validate(topic, version, msg.get("data", {})):
        return  # strict 模式下驗證失敗，丟棄

    category = parse_topic(topic)["category"]
    with metrics.processing_time(category):
        writer.write(topic, payload)
```

## 依賴套件

```bash
pip install psycopg2-binary pyyaml pandas pyarrow boto3 \
    prometheus_client jsonschema genson
```
