"""
UNS Platform Backend — Configuration
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    # --- Application ---
    app_name: str = "UNS Platform Backend"
    debug: bool = False

    # --- Database ---
    database_url: str = "postgresql+asyncpg://uns_admin:uns_dev_password@localhost:5432/uns_timeseries"

    # --- MQTT / EMQX ---
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    emqx_api_url: str = "http://localhost:18083"

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
