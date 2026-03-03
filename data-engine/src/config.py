"""
UNS Data Engine — Configuration

所有設定從環境變數讀取，提供合理的預設值。
"""

import os


class Config:
    """Data Engine 設定，從環境變數讀取。"""

    # ── MQTT ──────────────────────────────────────────────────
    MQTT_BROKER: str = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_CLIENT_ID: str = os.getenv("MQTT_CLIENT_ID", "uns-data-engine-01")
    MQTT_SUBSCRIBE_TOPIC: str = os.getenv("MQTT_SUBSCRIBE_TOPIC", "#")
    MQTT_QOS: int = int(os.getenv("MQTT_QOS", "1"))

    # ── Database ─────────────────────────────────────────────
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "uns_timeseries")
    DB_USER: str = os.getenv("DB_USER", "uns_admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "uns_dev_password")

    @classmethod
    def db_dsn(cls) -> dict:
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "dbname": cls.DB_NAME,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
        }

    # ── Batch Writer ─────────────────────────────────────────
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "100"))
    BATCH_INTERVAL_SEC: float = float(os.getenv("BATCH_INTERVAL_SEC", "1.0"))

    # ── Deadband ─────────────────────────────────────────────
    DEADBAND_ENABLED: bool = os.getenv("DEADBAND_ENABLED", "true").lower() == "true"

    # ── Bootstrap ────────────────────────────────────────────
    # 啟動後前 N 秒收到的 retained message 不寫 DB
    BOOTSTRAP_WINDOW_SEC: float = float(os.getenv("BOOTSTRAP_WINDOW_SEC", "5.0"))

    # ── Logging ──────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
