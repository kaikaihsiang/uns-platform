"""
UNS Data Engine — Entry Point

asyncio 入口：初始化 DB → Schema Matcher → Tag Lookup → Pipeline → MQTT Consumer
"""

import asyncio
import logging
import signal
from datetime import datetime, timedelta, timezone

from src.config import Config
from src.consumer import MQTTConsumer
from src.db_pool import DBPool
from src.pipeline import Pipeline

# ── Logging 設定 ──────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("uns.main")


async def main():
    logger.info("=" * 60)
    logger.info("UNS Data Engine starting...")
    logger.info("=" * 60)
    logger.info("MQTT Broker: %s:%d", Config.MQTT_BROKER, Config.MQTT_PORT)
    logger.info("Database: %s@%s:%d/%s", Config.DB_USER, Config.DB_HOST, Config.DB_PORT, Config.DB_NAME)
    logger.info("Batch size: %d, interval: %.1fs", Config.BATCH_SIZE, Config.BATCH_INTERVAL_SEC)
    logger.info("Deadband: %s", "enabled" if Config.DEADBAND_ENABLED else "disabled")

    # ── 初始化 DB Pool ──
    logger.info("Initializing DB connection pool...")
    db_pool = DBPool()

    # ── Bootstrap window ──
    bootstrap_until = datetime.now(timezone.utc) + timedelta(
        seconds=Config.BOOTSTRAP_WINDOW_SEC
    )
    logger.info("Bootstrap window until: %s", bootstrap_until.isoformat())

    # ── 建立 Pipeline ──
    pipeline = Pipeline(
        db_pool=db_pool,
        bootstrap_until=bootstrap_until,
    )

    # ── 建立 Consumer ──
    consumer = MQTTConsumer(pipeline)

    # ── Signal handler ──
    stop_event = asyncio.Event()

    def shutdown(sig):
        logger.info("Received signal %s, shutting down...", sig.name)
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown, sig)

    # ── 啟動 Consumer ──
    try:
        await consumer.start(stop_event)
    except Exception as e:
        logger.error("Consumer failed: %s", e, exc_info=True)
    finally:
        db_pool.close()
        logger.info("Database connection pool closed")
        logger.info("UNS Data Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())
