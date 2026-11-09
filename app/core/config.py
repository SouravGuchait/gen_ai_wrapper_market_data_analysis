import os
from functools import lru_cache
from typing import ClassVar

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )   
    log_file_path: str = os.getenv("LOG_FILE_PATH", os.path.join(os.path.dirname(__file__), "app.log"))
    app_name: str = "Market Data AI Service"
    environment: str = "development"
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )
    django_api_base_url: HttpUrl = HttpUrl("http://localhost:8000/")
    django_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    django_max_response_bytes: int = Field(default=1_048_576, gt=0, le=10_485_760)
    log_file_path = log_file_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
