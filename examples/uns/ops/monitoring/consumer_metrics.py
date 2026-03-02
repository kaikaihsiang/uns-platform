"""
consumer_metrics.py — UNS Consumer 的 Prometheus 指標模組

此模組提供可直接 import 到 consumer_example.py 使用的 Prometheus 指標。
只要 import 就會自動暴露 /metrics endpoint 在 port 8000。

用法：
    # 在 consumer_example.py 中
    from consumer_metrics import metrics

    # 收到訊息時
    with metrics.processing_time("Telemetry"):
        writer.write(topic, payload)

    # 錯誤時
    metrics.record_error("Telemetry", "db_error")

    # DB 狀態
    metrics.set_db_connected(True)

依賴套件：
    pip install prometheus_client
"""

import time
import logging
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    start_http_server,
    REGISTRY,
)

logger = logging.getLogger("uns_consumer.metrics")

METRICS_PORT = 8000


class ConsumerMetrics:
    """
    UNS Consumer 的 Prometheus 指標集合。

    指標分 4 類：
      - Counter   — 累計值（只增不減）
      - Histogram — 延遲分佈
      - Gauge     — 目前狀態
      - Info      — 靜態資訊
    """

    def __init__(self, port: int = METRICS_PORT):
        self.port = port
        self._started = False

        # ── 訊息處理 ──────────────────────────────────────
        self.messages_received = Counter(
            "uns_consumer_messages_total",
            "收到的 MQTT 訊息總數",
            ["category"]
        )

        self.messages_processed = Counter(
            "uns_consumer_messages_processed_total",
            "成功處理（寫入 DB）的訊息數",
            ["category"]
        )

        self.messages_errors = Counter(
            "uns_consumer_messages_errors_total",
            "處理失敗的訊息數",
            ["category", "error_type"]
        )

        self.messages_skipped = Counter(
            "uns_consumer_messages_skipped_total",
            "被跳過的訊息數（非 time-series category）",
            ["category"]
        )

        # ── 延遲（Processing Time） ──────────────────────
        self.processing_duration = Histogram(
            "uns_consumer_processing_seconds",
            "每筆訊息從收到到寫入 DB 的處理時間",
            ["category"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        )

        # ── Tag 管理 ─────────────────────────────────────
        self.active_tags = Gauge(
            "uns_consumer_active_tags",
            "目前 active 的 tag 數量"
        )

        self.tags_created = Counter(
            "uns_consumer_tags_created_total",
            "自動建立的 tag 數量"
        )

        # ── Schema 驗證 ──────────────────────────────────
        self.schema_validations = Counter(
            "uns_consumer_schema_validations_total",
            "Schema 驗證次數",
            ["result"]  # pass / fail / skipped
        )

        self.schema_validation_failures = Counter(
            "uns_consumer_schema_validation_failures_total",
            "Schema 驗證失敗次數",
            ["topic_pattern"]
        )

        # ── 系統狀態 ─────────────────────────────────────
        self.db_connected = Gauge(
            "uns_consumer_db_connected",
            "TimescaleDB 連線狀態 (1=connected, 0=disconnected)"
        )

        self.mqtt_connected = Gauge(
            "uns_consumer_mqtt_connected",
            "MQTT Broker 連線狀態 (1=connected, 0=disconnected)"
        )

        self.uptime_seconds = Gauge(
            "uns_consumer_uptime_seconds",
            "Consumer 運行時間（秒）"
        )

        # ── Consumer 資訊 ────────────────────────────────
        self.info = Info(
            "uns_consumer",
            "Consumer 實例資訊"
        )

    def start(self, consumer_id: str = "consumer-01"):
        """啟動 Prometheus HTTP server"""
        if self._started:
            return

        self.info.info({
            "consumer_id": consumer_id,
            "version": "1.0.0",
        })
        self.db_connected.set(0)
        self.mqtt_connected.set(0)

        start_http_server(self.port)
        self._started = True
        self._start_time = time.time()
        logger.info(f"Prometheus metrics 啟動在 :{self.port}/metrics")

    # ── 便利方法 ──────────────────────────────────────────

    @contextmanager
    def processing_time(self, category: str):
        """
        用 context manager 自動記錄處理時間。

        用法：
            with metrics.processing_time("Telemetry"):
                writer.write(topic, payload)
        """
        self.messages_received.labels(category=category).inc()
        start = time.time()
        try:
            yield
            self.messages_processed.labels(category=category).inc()
        except Exception:
            raise
        finally:
            duration = time.time() - start
            self.processing_duration.labels(category=category).observe(duration)

    def record_error(self, category: str, error_type: str):
        """記錄處理錯誤"""
        self.messages_errors.labels(
            category=category, error_type=error_type
        ).inc()

    def record_skip(self, category: str):
        """記錄跳過的訊息"""
        self.messages_skipped.labels(category=category).inc()

    def set_db_connected(self, connected: bool):
        """更新 DB 連線狀態"""
        self.db_connected.set(1 if connected else 0)

    def set_mqtt_connected(self, connected: bool):
        """更新 MQTT 連線狀態"""
        self.mqtt_connected.set(1 if connected else 0)

    def set_active_tags(self, count: int):
        """更新 active tag 數量"""
        self.active_tags.set(count)

    def record_tag_created(self):
        """記錄新 tag 建立"""
        self.tags_created.inc()

    def update_uptime(self):
        """更新運行時間（定期呼叫）"""
        if hasattr(self, "_start_time"):
            self.uptime_seconds.set(time.time() - self._start_time)


# ── 全域 singleton ────────────────────────────────────────
# import 後直接使用：
#   from consumer_metrics import metrics
#   metrics.start()

metrics = ConsumerMetrics()
