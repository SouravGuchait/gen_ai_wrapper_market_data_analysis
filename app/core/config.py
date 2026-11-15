import os
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field, HttpUrl
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


def _env_file() -> str | None:
    configured = os.getenv("APP_ENV_FILE", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path.home() / ".config" / "env_vars" / "dev-ai.env",
        Path(".env"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return str(candidate)
    return None


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )
    app_name: str = "Market Data AI Service"
    environment: str = "development"
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8002, ge=1, le=65535)
    django_api_base_url: HttpUrl = HttpUrl("http://localhost:8000/")
    django_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    django_max_response_bytes: int = Field(default=1_048_576, gt=0, le=10_485_760)
    # Override Host when base URL host is not in Django ALLOWED_HOSTS
    # (e.g. Docker uses host.docker.internal but Django allows 127.0.0.1).
    django_api_host_header: str | None = None
    log_file_path: str = Field(default="/var/log/ai/app.log", min_length=1)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del dotenv_settings
        env_file = _env_file()
        if env_file is None:
            return init_settings, env_settings, file_secret_settings
        return (
            init_settings,
            env_settings,
            DotEnvSettingsSource(
                settings_cls,
                env_file=env_file,
                env_file_encoding="utf-8",
            ),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
