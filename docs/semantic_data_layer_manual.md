# UNS 語義資料層操作手冊 (Semantic Data Access Layer)

> **版本：** 1.0 (2026-03-14)  
> **狀態：** 已上線  
> **相關決策紀錄：** [ADR-005: Semantic Data Access Layer](./adr/ADR-005-semantic-data-layer.md)

---

## 1. 簡介 (Overview)

UNS 語義資料層（Semantic Data Layer）是本平台的工業語義網關。其核心目標是實現「**路徑即語義 (Path-as-Semantic)**」的數據存取，讓外部系統（如 AI Agent、MES、ERP 或邊緣運算）不需要理解底層資料庫的 `tag_id` 或複雜的超表結構，即可透過 ISA-95 資產路徑進行高速存取。

### 核心功能
*   **高速快照 (GetSnapshot)**：基於 `latest_values` 緩存表，提供 sub-second 級別的全廠/全線狀態查詢。
*   **語義寫回 (PublishData)**：直接透過語義路徑發布資料，系統自動轉換為 MQTT Topic 並完成持久化。
*   **屬性搜尋 (SearchNamespace)**：基於資產元數據（Metadata）反查路徑。

---

## 2. REST API 介面

後端提供標準 REST API 供 Web 應用程式或簡單腳本呼叫。

### 2.1 取得路徑快照 (GetSnapshot)
支援使用萬用字元（Wildcards `*`, `**`）進行批次查詢。

*   **Endpoint:** `GET /api/v1/semantic/snapshot`
*   **參數:**
    *   `paths`: 路徑清單 (例如: `TaiwanPrecision/Taoyuan/SMT_Line_1/**`)
*   **範例呼叫:**
    ```bash
    curl "http://localhost:8000/api/v1/semantic/snapshot?paths=TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/**"
    ```
*   **回傳格式:**
    ```json
    [
      {
        "path": "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Status/Status",
        "tag_id": "6",
        "ts": "2026-03-14T01:38:08+00:00",
        "value": "STANDBY",
        "semantic_label": "equipment_state",
        "unit": "--",
        "metadata": {},
        "run_id": "8"
      }
    ]
    ```

### 2.2 語義發布 (PublishData)
透過語義路徑將資料寫回 UNS。

*   **Endpoint:** `POST /api/v1/semantic/publish`
*   **Body:**
    ```json
    {
      "path": "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Status",
      "value": {
        "data": {
          "state": "RUNNING",
          "sub_state": "PRD",
          "mode": "AUTO"
        }
      }
    }
    ```
*   **範例呼叫:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/semantic/publish" \
         -H "Content-Type: application/json" \
         -d '{"path": "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Status", "value": {"data": {"state": "RUNNING"}}}'
    ```

---

## 3. gRPC 介面 (高效能整合)

針對 AI Agent 或工業邊緣網關，建議使用 gRPC 介面。

*   **監聽位址:** `localhost:50051`
*   **Proto 檔案:** `backend/app/proto/uns_data_service.proto`

### 3.1 Python 呼叫範例

```python
import grpc
from app.proto import uns_data_service_pb2, uns_data_service_pb2_grpc

async def run():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = uns_data_service_pb2_grpc.UNSDataServiceStub(channel)
        
        # 1. 取得快照
        request = uns_data_service_pb2.GetSnapshotRequest(
            paths=["TaiwanPrecision/**/Status"]
        )
        response = await stub.GetSnapshot(request)
        for point in response.points:
            print(f"Path: {point.path}, Value: {point.raw_value}")

        # 2. 發布資料
        pub_req = uns_data_service_pb2.PublishDataRequest(
            path="TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Telemetry/temp",
            value=uns_data_service_pb2.google_dot_protobuf_dot_struct__pb2.Value(number_value=25.5)
        )
        pub_res = await stub.PublishData(pub_req)
        print(f"Success: {pub_res.success}")
```

---

## 4. 效能優化：Latest Values 緩存機制

為了應對大規模 Tag（>10,000）的高頻查詢，我們在 Data Engine 層實作了 **UPSERT 緩存機制**：

1.  **寫入時觸發**：當 Data Engine 接收到任何 MQTT 數據並準備寫入時序超表（Hypertables）時，會同步將該 Tag 的最新值更新到 `latest_values` 平面表。
2.  **時序保證**：UPSERT 語法包含 `WHERE EXCLUDED.time >= latest_values.time`，確保只有較新的數據會覆蓋緩存，防止因網路延遲導致的數據倒灌。
3.  **零跨表開銷**：`GetSnapshot` 呼叫僅查詢 `latest_values` 表，完全避免了對大型時序表執行 `ORDER BY time DESC LIMIT 1` 的高昂代價。

---

## 5. 互動式文件

您可以啟動 Backend 服務後，透過 Swagger UI 瀏覽完整的 API 定義：
👉 [http://localhost:8000/docs](http://localhost:8000/docs) (尋找 **Semantic** 標籤)
