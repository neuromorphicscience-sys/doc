from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "公文格式智能规范化系统 API"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_fallback_model: str = "deepseek-v4-pro"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    task_data_dir: Path = Path("./backend/data/tasks")
    task_retention_hours: int = Field(default=24, ge=1, le=168)
    max_upload_bytes: int = 20 * 1024 * 1024
    max_uncompressed_bytes: int = 120 * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
