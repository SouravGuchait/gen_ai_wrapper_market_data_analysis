import asyncio
from dataclasses import dataclass
from typing import Protocol
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from app.core.config import Settings
from app.llm.exceptions import (
    InvalidProviderResponse,
    LLMError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnexpectedProviderError,
)
from app.llm.factory import create_llm_provider, provider_config
from app.llm.http import http_error
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.schemas import GenerationConfig, LLMResponse

_SECRET = "sk-test-secret"
_CONFIG = GenerationConfig(temperature=0.0, max_output_tokens=32, timeout_seconds=5.0)


@dataclass
class Generated:
    result: LLMResponse | None
    error: Exception | None
    mock: AsyncMock
    delays: list[float]


def _settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "llm_provider": "xai",
        "llm_model_id": "configured-model",
        "llm_api_key": _SECRET,
        "llm_base_url": "https://example.invalid/v1",
        "llm_max_output_tokens": 32,
        "llm_timeout_seconds": 5.0,
        "llm_max_retries": 0,
    }
    payload.update(overrides)
    return Settings.model_validate(payload)


def _completion(
    content: str | None,
    *,
    usage: CompletionUsage | None,
    choices: list[Choice] | None = None,
) -> ChatCompletion:
    selected = choices
    if selected is None:
        selected = [
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content=content),
                finish_reason="stop",
            )
        ]
    return ChatCompletion(
        id="provider-request-1",
        choices=selected,
        created=1,
        model="configured-model",
        object="chat.completion",
        usage=usage,
    )


def _usage() -> CompletionUsage:
    return CompletionUsage(prompt_tokens=20, completion_tokens=50, total_tokens=70)


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://example.invalid/v1/chat/completions")


class _StatusError(Protocol):
    def __call__(self, message: str, *, response: httpx.Response, body: object) -> Exception: ...


def _http_error(status_code: int, error_type: _StatusError, message: str) -> Exception:
    response = httpx.Response(status_code, request=_request())
    return error_type(message, response=response, body={"api_key": _SECRET})


async def _generate(
    *,
    result: ChatCompletion | None = None,
    error: Exception | None = None,
    sequence: list[object] | None = None,
    max_retries: int = 0,
    provider_name: str = "xai",
) -> Generated:
    delays: list[float] = []

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    client = AsyncOpenAI(api_key="unused", base_url="https://example.invalid/v1", max_retries=0)
    provider = OpenAICompatibleProvider(
        provider_config(_settings(llm_provider=provider_name, llm_max_retries=max_retries)),
        client,
        sleeper,
    )
    mock = AsyncMock()
    if sequence is not None:
        mock.side_effect = sequence
    elif error is not None:
        mock.side_effect = error
    else:
        mock.return_value = result
    caught: Exception | None = None
    generated: LLMResponse | None = None
    try:
        with patch.object(client.chat.completions, "create", mock):
            generated = await provider.generate(
                system_message="system",
                user_message="Explain what a moving average is",
                config=_CONFIG,
            )
    except Exception as exc:
        caught = exc
    finally:
        await provider.aclose()
    return Generated(result=generated, error=caught, mock=mock, delays=delays)


def _run(
    *,
    result: ChatCompletion | None = None,
    error: Exception | None = None,
    sequence: list[object] | None = None,
    max_retries: int = 0,
    provider_name: str = "xai",
) -> Generated:
    return asyncio.run(
        _generate(
            result=result,
            error=error,
            sequence=sequence,
            max_retries=max_retries,
            provider_name=provider_name,
        )
    )


def test_successful_response_is_normalized() -> None:
    generated = _run(result=_completion("A moving average smooths prices.", usage=_usage()))
    result = generated.result

    assert generated.error is None
    assert result is not None
    assert result.text == "A moving average smooths prices."
    assert result.provider == "xai"
    assert result.model == "configured-model"
    assert result.finish_reason == "stop"
    assert result.request_id == "provider-request-1"
    assert result.duration_seconds >= 0
    assert result.usage is not None
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 50
    assert result.usage.total_tokens == 70
    call = generated.mock.await_args
    assert call is not None
    messages = call.kwargs["messages"]
    assert messages[1]["content"] == "Explain what a moving average is"
    assert call.kwargs["model"] == "configured-model"
    assert call.kwargs["extra_headers"] == {}
    assert _SECRET not in repr(result)


def test_token_usage_can_be_absent() -> None:
    generated = _run(result=_completion("A moving average smooths prices.", usage=None))

    assert generated.result is not None
    assert generated.result.usage.input_tokens == 0
    assert generated.result.usage.output_tokens == 0
    assert generated.result.usage.total_tokens == 0


@pytest.mark.parametrize(
    "completion",
    [
        _completion(None, usage=_usage()),
        _completion("   ", usage=_usage()),
        _completion("ignored", usage=_usage(), choices=[]),
    ],
)
def test_empty_provider_response_is_rejected(completion: ChatCompletion) -> None:
    generated = _run(result=completion)

    assert isinstance(generated.error, InvalidProviderResponse)


@pytest.mark.parametrize(
    ("error", "expected", "status_code"),
    [
        (
            _http_error(429, RateLimitError, f"slow down {_SECRET}"),
            ProviderRateLimitError,
            429,
        ),
        (APITimeoutError(request=_request()), ProviderTimeoutError, 504),
        (APIConnectionError(request=_request()), ProviderUnavailableError, 503),
        (_http_error(503, InternalServerError, "down"), ProviderUnavailableError, 503),
        (
            _http_error(401, AuthenticationError, f"bad {_SECRET}"),
            ProviderAuthenticationError,
            502,
        ),
        (_http_error(400, BadRequestError, "bad request"), UnexpectedProviderError, 502),
    ],
)
def test_provider_errors_are_normalized(
    error: Exception,
    expected: type[LLMError],
    status_code: int,
) -> None:
    generated = _run(error=error)

    assert isinstance(generated.error, expected)
    mapped_status, message = http_error(generated.error)
    assert mapped_status == status_code
    assert _SECRET not in message
    assert _SECRET not in str(generated.error)


def test_timeout_is_retried_and_authentication_failure_is_not() -> None:
    success = _completion("Recovered.", usage=None)
    timeout = _run(
        sequence=[APITimeoutError(request=_request()), success],
        max_retries=1,
    )
    assert timeout.error is None
    assert timeout.result is not None
    assert timeout.result.text == "Recovered."
    assert timeout.mock.await_count == 2
    assert timeout.delays == [0.25]

    denied = _run(
        error=_http_error(401, AuthenticationError, "nope"),
        max_retries=1,
    )
    assert isinstance(denied.error, ProviderAuthenticationError)
    assert denied.mock.await_count == 1
    assert denied.delays == []


def test_openrouter_headers_are_sent() -> None:
    async def call() -> AsyncMock:
        client = AsyncOpenAI(api_key="unused", base_url="https://openrouter.example/api/v1")

        async def sleeper(_delay: float) -> None:
            return None

        provider = OpenAICompatibleProvider(
            provider_config(
                _settings(
                    llm_provider="openrouter",
                    openrouter_api_key="openrouter-test-key",
                    openrouter_base_url="https://openrouter.example/api/v1",
                    openrouter_http_referer="https://app.example",
                    openrouter_app_title="Market Data AI",
                )
            ),
            client,
            sleeper,
        )
        mock = AsyncMock(return_value=_completion("ok", usage=None))
        try:
            with patch.object(client.chat.completions, "create", mock):
                await provider.generate(
                    system_message="system",
                    user_message="hello",
                    config=_CONFIG,
                )
        finally:
            await provider.aclose()
        return mock

    mock = asyncio.run(call())
    call_args = mock.await_args
    assert call_args is not None
    headers = call_args.kwargs["extra_headers"]
    assert headers["HTTP-Referer"] == "https://app.example"
    assert headers["X-Title"] == "Market Data AI"


def test_provider_repr_hides_the_api_key() -> None:
    provider = create_llm_provider(_settings())
    try:
        assert _SECRET not in repr(provider)
        assert _SECRET not in repr(provider._config)
    finally:
        asyncio.run(provider.aclose())
