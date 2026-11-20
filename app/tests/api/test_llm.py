from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI, AuthenticationError, RateLimitError
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from app.api.dependencies import logger as dependency_logger
from app.clients.django import DjangoClient
from app.core.config import Settings, get_settings
from app.llm.factory import provider_config
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.rate_limit import RateLimiter
from app.main import app
from app.services.llm_service import logger as llm_logger

_SECRET = "sk-test-secret"
_PROMPT = "Explain what a moving average is"


def _completion() -> ChatCompletion:
    return ChatCompletion(
        id="provider-request-1",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content="A moving average smooths prices.",
                ),
                finish_reason="stop",
            )
        ],
        created=1,
        model="configured-model",
        object="chat.completion",
        usage=CompletionUsage(prompt_tokens=20, completion_tokens=50, total_tokens=70),
    )


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "llm_provider": "xai",
            "llm_model_id": "configured-model",
            "llm_api_key": _SECRET,
            "llm_base_url": "https://example.invalid/v1",
            "llm_max_output_tokens": 64,
            "llm_timeout_seconds": 5.0,
            "llm_max_retries": 0,
        }
    )


def _clear_state() -> None:
    for name in ("django_client", "llm_provider", "llm_rate_limiter"):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _prepare(
    *,
    django_status: int = 200,
    limit: int = 10,
    configure_provider: bool = True,
) -> tuple[AsyncOpenAI | None, AsyncMock | None]:
    async def handler(_request: httpx.Request) -> httpx.Response:
        if django_status == 200:
            return httpx.Response(200, json={"id": 21, "username": "alice"})
        return httpx.Response(django_status, json={"detail": "private"})

    app.state.django_client = DjangoClient(
        "http://django.test/",
        transport=httpx.MockTransport(handler),
    )
    app.state.llm_rate_limiter = RateLimiter(limit, 60)
    if not configure_provider:
        return None, None
    client = AsyncOpenAI(api_key="unused", base_url="https://example.invalid/v1", max_retries=0)

    async def sleeper(_delay: float) -> None:
        return None

    app.state.llm_provider = OpenAICompatibleProvider(provider_config(_settings()), client, sleeper)
    return client, AsyncMock(return_value=_completion())


def test_llm_test_requires_authentication() -> None:
    sdk, mock = _prepare()
    assert sdk is not None
    assert mock is not None
    try:
        with patch.object(sdk.chat.completions, "create", mock), TestClient(app) as client:
            response = client.post("/api/v1/llm/test", json={"message": _PROMPT})
    finally:
        _clear_state()

    assert response.status_code == 401
    assert _SECRET not in response.text


def test_llm_test_rejects_invalid_django_token() -> None:
    sdk, mock = _prepare(django_status=401)
    assert sdk is not None
    assert mock is not None
    try:
        with patch.object(sdk.chat.completions, "create", mock), TestClient(app) as client:
            response = client.post(
                "/api/v1/llm/test",
                json={"message": _PROMPT},
                headers={"Authorization": "Bearer test-access-token"},
            )
    finally:
        _clear_state()

    assert response.status_code == 401
    assert mock.await_count == 0
    assert _SECRET not in response.text


def test_llm_test_returns_normalized_response() -> None:
    sdk, mock = _prepare()
    assert sdk is not None
    assert mock is not None
    try:
        with (
            patch.object(sdk.chat.completions, "create", mock),
            patch.object(llm_logger, "info") as log_info,
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/llm/test",
                json={"message": _PROMPT},
                headers={"Authorization": "Bearer test-access-token"},
            )
    finally:
        _clear_state()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["errors"] == []
    assert body["data"]["response"] == "A moving average smooths prices."
    assert body["data"]["provider"] == "xai"
    assert body["data"]["model"] == "configured-model"
    assert body["data"]["usage"] == {
        "input_tokens": 20,
        "output_tokens": 50,
        "total_tokens": 70,
    }
    assert body["data"]["request_id"] == "provider-request-1"
    rendered = " ".join(str(call) for call in log_info.call_args_list)
    assert _SECRET not in response.text
    assert _PROMPT not in rendered
    assert "test-access-token" not in rendered


def test_llm_test_rejects_invalid_input() -> None:
    sdk, mock = _prepare()
    assert sdk is not None
    assert mock is not None
    try:
        with patch.object(sdk.chat.completions, "create", mock), TestClient(app) as client:
            response = client.post(
                "/api/v1/llm/test",
                json={"message": "  "},
                headers={"Authorization": "Bearer test-access-token"},
            )
    finally:
        _clear_state()

    assert response.status_code == 422
    assert mock.await_count == 0
    assert _SECRET not in response.text


def test_llm_test_reports_provider_failures_without_sdk_text() -> None:
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    limited = RateLimitError(
        f"slow down {_SECRET}",
        response=httpx.Response(429, request=request),
        body=None,
    )
    denied = AuthenticationError(
        f"bad {_SECRET}",
        response=httpx.Response(401, request=request),
        body=None,
    )
    sdk, _mock = _prepare()
    assert sdk is not None
    assert _mock is not None
    try:
        with (
            patch.object(sdk.chat.completions, "create", AsyncMock(side_effect=[limited, denied])),
            TestClient(app) as client,
        ):
            headers = {"Authorization": "Bearer test-access-token"}
            rate_response = client.post(
                "/api/v1/llm/test", json={"message": _PROMPT}, headers=headers
            )
            auth_response = client.post(
                "/api/v1/llm/test", json={"message": _PROMPT}, headers=headers
            )
    finally:
        _clear_state()

    assert rate_response.status_code == 429
    assert rate_response.json()["errors"] == ["LLM provider rate limit exceeded"]
    assert auth_response.status_code == 502
    assert auth_response.json()["errors"] == ["LLM provider rejected the credentials"]
    assert _SECRET not in rate_response.text
    assert _SECRET not in auth_response.text


def test_local_throttle_uses_one_limiter_instance() -> None:
    sdk, mock = _prepare(limit=1)
    assert sdk is not None
    assert mock is not None
    try:
        with patch.object(sdk.chat.completions, "create", mock), TestClient(app) as client:
            headers = {"Authorization": "Bearer test-access-token"}
            first = client.post("/api/v1/llm/test", json={"message": _PROMPT}, headers=headers)
            second = client.post("/api/v1/llm/test", json={"message": _PROMPT}, headers=headers)
    finally:
        _clear_state()

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["errors"] == ["Too many LLM requests"]
    assert _SECRET not in second.text


def test_missing_provider_configuration_is_a_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("LLM_API_KEY", _SECRET)
    get_settings.cache_clear()
    _prepare(configure_provider=False)
    try:
        with patch.object(dependency_logger, "info") as log_info, TestClient(app) as client:
            response = client.post(
                "/api/v1/llm/test",
                json={"message": _PROMPT},
                headers={"Authorization": "Bearer test-access-token"},
            )
    finally:
        get_settings.cache_clear()
        _clear_state()

    assert response.status_code == 503
    assert response.json()["errors"] == ["LLM provider is not configured"]
    rendered = " ".join(str(call) for call in log_info.call_args_list)
    assert _SECRET not in rendered
    assert _SECRET not in response.text
