# CDC (Change Data Capture) 範例：MES PostgreSQL → UNS

## 概述

此範例展示如何用 **Debezium CDC** 零侵入地將 MES 的事件資料自動發佈到 UNS。

**核心價值：不需要改 MES 的任何一行程式碼。**

```
MES PostgreSQL                Debezium              Transform             MQTT Broker
┌────────────┐              ┌──────────┐           ┌───────────┐         ┌──────────┐
│ lot 表      │── binlog ──►│ Connector │──JSON──►  │ DB Row →   │──MQTT──►│ UNS      │
│ equipment 表│              │           │           │ UNS 信封   │         │          │
│ event_      │              │           │           │            │         │          │
│ tracking 表│              │           │           │            │         │          │
└────────────┘              └──────────┘           └───────────┘         └──────────┘
  MES 工程師                   基礎設施               你寫的                  既有
  完全不用改                   Docker 部署            Transform Rules
```

## 檔案結構

```
cdc_mes_bridge/
├── README.md                  ← 你正在看的這個檔案
├── docker-compose.yml         ← 一鍵啟動 Debezium + Kafka Connect
├── mes_sample_schema.sql      ← MES 的範例 DB schema（模擬用）
├── debezium_connector.json    ← Debezium PostgreSQL 連接器設定
└── transform_service.py       ← MES DB Row → UNS MQTT Payload 轉換服務
```

## 快速啟動

```bash
# 1. 啟動基礎設施（Debezium + Kafka + MQTT Broker）
docker-compose up -d

# 2. 建立 MES 範例 DB
psql -h localhost -U mes -d mes_db -f mes_sample_schema.sql

# 3. 註冊 Debezium Connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @debezium_connector.json

# 4. 啟動 Transform Service
pip install psycopg2-binary paho-mqtt confluent-kafka
python transform_service.py
```

## 運作流程

1. MES 執行 LotMoveIn → 寫入 `event_tracking` 表
2. PostgreSQL 的 WAL (Write-Ahead Log) 記錄這筆 INSERT
3. Debezium 讀取 WAL → 產生 Change Event (JSON)
4. Transform Service 接收 Change Event
5. Transform Service 轉換成 UNS 信封格式
6. Publish 到 MQTT Broker 的對應 topic
7. UNS Consumer 存入 TimescaleDB
