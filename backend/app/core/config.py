"""
UNS Platform Backend — Configuration
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    # --- Application ---
    app_name: str = "UNS Platform Backend"
    platform_version: str = "0.1.0"
    debug: bool = False

    # --- Database ---
    database_url: str = "postgresql+asyncpg://uns_admin:uns_dev_password@localhost:5432/uns_timeseries"
    test_database_url: str = "postgresql+asyncpg://uns_admin:uns_dev_password@localhost:5432/uns_test"

    # --- MQTT / EMQX ---
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    emqx_api_url: str = "http://localhost:18083"
    emqx_api_user: str = "admin"
    emqx_api_password: str = "public"

    # --- AI / LLM ---
    gemini_api_key: str = "AIzaSyBQ30mefdj2Ub5qamY1KcGPK8n8jpOmsTc"
    llm_provider: str = "gemini"  # "gemini" | "openai" (Phase 2)

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
