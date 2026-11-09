import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings.model_validate({})
    assert str(settings.django_api_base_url) == "http://localhost:8000/"
    assert settings.django_timeout_seconds == 10


def test_settings_reject_nonpositive_timeout() -> None:
    with pytest.raises(ValidationError):
        _ = Settings.model_validate({"django_timeout_seconds": 0})


def test_settings_reject_unknown_log_level() -> None:
    with pytest.raises(ValidationError):
        _ = Settings.model_validate({"log_level": "TRACE"})
