import asyncio
import logging

import pytest

from app.llm.exceptions import LocalRateLimitError, ProviderTimeoutError
from app.llm.rate_limit import RateLimiter
from app.llm.schemas import GenerationConfig, LLMRequest, LLMResponse, TokenUsage
from app.schemas.django_user import DjangoAuthMe
from app.services.llm_service import audit_user_id, run_llm_test

_PROMPT = "secret prompt text that must stay out of logs"


class _Provider:
    def __init__(self, result: LLMResponse | None = None, error: Exception | None = None) -> None:
        self.provider_name = "xai"
        self.model_id = "configured-model"
        self.result = result
        self.error = error
        self.user_message = ""

    async def generate(
        self,
        *,
        system_message: str,
        user_message: str,
        config: GenerationConfig,
    ) -> LLMResponse:
        del system_message, config
        self.user_message = user_message
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise ProviderTimeoutError("LLM provider timed out")
        return self.result

    async def aclose(self) -> None:
        return None


def _request(user_id: str = "21") -> LLMRequest:
    return LLMRequest(
        message=_PROMPT,
        config=GenerationConfig(temperature=0.0, max_output_tokens=32, timeout_seconds=5.0),
        request_id="request-1",
        user_id=user_id,
    )


def _result(usage: TokenUsage) -> LLMResponse:
    return LLMResponse(
        text="A moving average smooths prices.",
        provider="xai",
        model="configured-model",
        finish_reason="stop",
        usage=usage,
        request_id="provider-request-1",
        duration_seconds=0.01,
    )


def test_service_logs_success_without_the_prompt_or_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = _Provider(
        result=_result(TokenUsage(input_tokens=20, output_tokens=50, total_tokens=70))
    )
    with caplog.at_level(logging.INFO):
        result = asyncio.run(run_llm_test(provider, RateLimiter(2, 60), _request()))

    assert result.text == "A moving average smooths prices."
    assert provider.user_message == _PROMPT
    assert _PROMPT not in caplog.text
    assert "sk-" not in caplog.text
    assert "llm_succeeded" in caplog.text
    assert "user_id=21" in caplog.text
    assert "input_tokens=20" in caplog.text
    assert "output_tokens=50" in caplog.text
    assert "total_tokens=70" in caplog.text


def test_service_logs_absent_usage_and_failure_type(caplog: pytest.LogCaptureFixture) -> None:
    provider = _Provider(error=ProviderTimeoutError(f"timed out leaking {_PROMPT}"))
    with caplog.at_level(logging.INFO), pytest.raises(ProviderTimeoutError):
        asyncio.run(run_llm_test(provider, RateLimiter(2, 60), _request()))

    assert _PROMPT not in caplog.text
    assert "error=ProviderTimeoutError" in caplog.text
    assert "llm_failed" in caplog.text


def test_service_throttles_before_calling_the_provider(caplog: pytest.LogCaptureFixture) -> None:
    provider = _Provider(result=_result(usage=TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)))
    limiter = RateLimiter(1, 60)
    with caplog.at_level(logging.INFO):
        asyncio.run(run_llm_test(provider, limiter, _request()))
        with pytest.raises(LocalRateLimitError):
            asyncio.run(run_llm_test(provider, limiter, _request()))

    assert provider.user_message == _PROMPT
    assert "llm_throttled" in caplog.text
    assert _PROMPT not in caplog.text


def test_audit_user_id_uses_auth_me_payload() -> None:
    assert audit_user_id(DjangoAuthMe.model_validate({"id": 21, "username": "alice"})) == "21"
    nested = DjangoAuthMe.model_validate({"success": True, "data": {"id": "user-7"}})
    assert audit_user_id(nested) == "user-7"
    assert audit_user_id(DjangoAuthMe.model_validate({"username": "alice"})) == "unknown"


def test_rate_limiter_expires_old_events() -> None:
    limiter = RateLimiter(1, 10)
    assert limiter.allow("21", now=1.0) is True
    assert limiter.allow("21", now=2.0) is False
    assert limiter.allow("21", now=12.0) is True
