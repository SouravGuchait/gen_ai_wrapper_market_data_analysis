import asyncio

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.llm.exceptions import (
    InvalidProviderConfiguration,
    MissingCredentials,
    UnsupportedProvider,
)
from app.llm.factory import create_llm_provider


def _settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "llm_provider": "xai",
        "llm_model_id": "configured-model",
        "llm_api_key": "xai-test-key",
        "llm_base_url": "https://example.invalid/v1",
        "llm_temperature": 0.0,
        "llm_max_output_tokens": 32,
        "llm_timeout_seconds": 5.0,
        "llm_max_retries": 0,
        "openrouter_api_key": "openrouter-test-key",
        "openrouter_base_url": "https://openrouter.example/api/v1",
        "openrouter_http_referer": "https://app.example",
        "openrouter_app_title": "Market Data AI",
    }
    payload.update(overrides)
    return Settings.model_validate(payload)


def test_xai_provider_initialization() -> None:
    provider = create_llm_provider(_settings())
    try:
        assert provider.provider_name == "xai"
        assert provider.model_id == "configured-model"
        assert provider.base_url == "https://example.invalid/v1"
        assert provider.extra_headers == ()
        assert str(provider._client.base_url).rstrip("/") == "https://example.invalid/v1"
        assert "xai-test-key" not in repr(provider)
    finally:
        asyncio.run(provider.aclose())


def test_openrouter_provider_initialization() -> None:
    provider = create_llm_provider(_settings(llm_provider="OpenRouter"))
    try:
        assert provider.provider_name == "openrouter"
        assert provider.model_id == "configured-model"
        assert provider.base_url == "https://openrouter.example/api/v1"
        assert provider.extra_headers == (
            ("HTTP-Referer", "https://app.example"),
            ("X-Title", "Market Data AI"),
        )
        assert "openrouter-test-key" not in repr(provider)
    finally:
        asyncio.run(provider.aclose())


def test_provider_factory_selects_credentials_for_the_configured_provider() -> None:
    xai = create_llm_provider(_settings())
    openrouter = create_llm_provider(_settings(llm_provider="openrouter"))
    try:
        assert xai.provider_name == "xai"
        assert openrouter.provider_name == "openrouter"
        assert xai._client.api_key == "xai-test-key"
        assert openrouter._client.api_key == "openrouter-test-key"
    finally:
        asyncio.run(xai.aclose())
        asyncio.run(openrouter.aclose())


def test_unsupported_provider_is_rejected() -> None:
    with pytest.raises(UnsupportedProvider) as caught:
        _ = create_llm_provider(_settings(llm_provider="bedrock"))

    assert "bedrock" not in str(caught.value)


def test_missing_api_key_is_rejected_for_the_selected_provider() -> None:
    with pytest.raises(MissingCredentials) as caught:
        _ = create_llm_provider(
            _settings(llm_api_key="", openrouter_api_key="openrouter-should-stay-hidden")
        )

    assert "openrouter-should-stay-hidden" not in str(caught.value)
    with pytest.raises(MissingCredentials):
        _ = create_llm_provider(
            _settings(llm_provider="openrouter", openrouter_api_key=SecretStr(""))
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_provider": ""},
        {"llm_model_id": " "},
        {"llm_model_id": "configured model"},
        {"llm_base_url": "ftp://example.invalid/v1"},
        {"llm_provider": "openrouter", "openrouter_base_url": ""},
    ],
)
def test_invalid_provider_configuration_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidProviderConfiguration):
        _ = create_llm_provider(_settings(**overrides))


def test_settings_reject_generation_values_outside_bounds() -> None:
    with pytest.raises(ValidationError):
        _ = _settings(llm_temperature=3)
    with pytest.raises(ValidationError):
        _ = _settings(llm_max_retries=4)
