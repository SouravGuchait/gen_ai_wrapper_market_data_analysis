from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, _env_file


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_FILE_PATH", raising=False)
    monkeypatch.setattr("app.core.config._env_file", lambda: None)
    settings = Settings.model_validate({})
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8002
    assert str(settings.django_api_base_url) == "http://localhost:8000/"
    assert settings.django_api_host_header is None
    assert settings.django_timeout_seconds == 10
    assert settings.log_file_path == "/var/log/ai/app.log"


def test_settings_reject_port_outside_range() -> None:
    with pytest.raises(ValidationError):
        _ = Settings.model_validate({"app_port": 0})


def test_explicit_env_file_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "service.env"
    env_file.write_text("APP_PORT=8002\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV_FILE", str(env_file))
    assert _env_file() == str(env_file)


def test_settings_reject_nonpositive_timeout() -> None:
    with pytest.raises(ValidationError):
        _ = Settings.model_validate({"django_timeout_seconds": 0})


def test_settings_reject_unknown_log_level() -> None:
    with pytest.raises(ValidationError):
        _ = Settings.model_validate({"log_level": "TRACE"})
