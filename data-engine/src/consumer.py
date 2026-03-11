"""
UNS Data Engine — MQTT Consumer

使用 gmqtt (async MQTT client) 訂閱所有 topic。
gmqtt 內建自動重連機制。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from gmqtt import Client as MQTTClient

from .config import Config
from .pipeline import Pipeline

logger = logging.getLogger("uns.consumer")


class MQTTConsumer:
    """
    MQTT Consumer — 訂閱 EMQX 所有 topic，收到訊息後交給 Pipeline 處理。

    使用 gmqtt 的內建 reconnect 機制（斷線自動重連）。
    """

    def __init__(self, pipeline: Pipeline):
        self._pipeline = pipeline
        self._client: Optional[MQTTClient] = None
        self._connected = False
        self._message_count = 0

    async def start(self, stop_event: asyncio.Event):
        """啟動 MQTT Consumer。"""
        self._client = MQTTClient(Config.MQTT_CLIENT_ID)

        # 設定 callback
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # gmqtt reconnect 設定
        self._client.set_config({
            "reconnect_retries": -1,       # 無限重試
            "reconnect_delay": 5,          # 初始重試間隔 5 秒
        })

        logger.info(
            "Connecting to MQTT broker: %s:%d",
            Config.MQTT_BROKER,
            Config.MQTT_PORT,
        )
        await self._client.connect(Config.MQTT_BROKER, Config.MQTT_PORT)

        # 啟動定期 flush
        flush_task = asyncio.create_task(self._periodic_flush(stop_event))

        # 等待停止信號 (修正：確保這這裡會阻塞直到收到停止信號)
        logger.info("MQTT Consumer is running. Waiting for stop signal...")
        while not stop_event.is_set():
            await asyncio.sleep(1)

        # 停止
        flush_task.cancel()
        try:
            await flush_task
        except asyncio.CancelledError:
            pass

        await self._client.disconnect()
        self._pipeline.close()
        logger.info("MQTT Consumer stopped. Stats: %s", self._pipeline.stats)

    def _on_connect(self, client, flags, rc, properties):
        """連線成功。"""
        self._connected = True
        logger.info("Connected to MQTT broker (rc=%d)", rc)
        client.subscribe(Config.MQTT_SUBSCRIBE_TOPIC, qos=Config.MQTT_QOS)
        logger.info("Subscribed to: %s", Config.MQTT_SUBSCRIBE_TOPIC)

    def _on_disconnect(self, client, packet, exc=None):
        """連線中斷。"""
        self._connected = False
        if exc:
            logger.warning("Disconnected from MQTT broker: %s", exc)
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, topic, payload, qos, properties):
        logger.info("RAW_MQTT_MSG: topic=%s", topic)
        """收到訊息，交給 Pipeline 處理。"""
        self._message_count += 1
        receive_time = datetime.now(timezone.utc)

        try:
            self._pipeline.process(topic, payload, receive_time)
        except Exception as e:
            logger.error("Pipeline error for topic %s: %s", topic, e, exc_info=True)

        # 每 1000 筆 log 一次統計
        if self._message_count % 1000 == 0:
            logger.info(
                "Processed %d messages. Stats: %s",
                self._message_count,
                self._pipeline.stats,
            )

        return 0  # gmqtt 要求回傳 0 表示 ACK

    async def _periodic_flush(self, stop_event: asyncio.Event):
        """定期 flush DB writer buffer。"""
        while not stop_event.is_set():
            try:
                await asyncio.sleep(Config.BATCH_INTERVAL_SEC)
                self._pipeline.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Periodic flush error: %s", e)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def message_count(self) -> int:
        return self._message_count
