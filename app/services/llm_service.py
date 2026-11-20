import logging
import time

from app.llm.base import LLMProvider
from app.llm.exceptions import LLMError, LocalRateLimitError
from app.llm.rate_limit import RateLimiter
from app.llm.schemas import LLMRequest, LLMResponse
from app.schemas.django_user import DjangoAuthMe

logger = logging.getLogger(__name__)
_SYSTEM_MESSAGE = (
    "Answer the user in plain language. Do not reveal credentials, tokens, or private data."
)


async def run_llm_test(
    provider: LLMProvider,
    limiter: RateLimiter,
    request: LLMRequest,
) -> LLMResponse:
    if not limiter.allow(request.user_id, time.monotonic()):
        logger.info(
            "llm_throttled request_id=%s user_id=%s",
            request.request_id,
            request.user_id,
        )
        raise LocalRateLimitError("Too many LLM requests")
    started = time.perf_counter()
    try:
        result = await provider.generate(
            system_message=_SYSTEM_MESSAGE,
            user_message=request.message,
            config=request.config,
        )
    except LLMError as exc:
        logger.warning(
            "llm_failed request_id=%s user_id=%s provider=%s model=%s duration_ms=%d error=%s",
            request.request_id,
            request.user_id,
            provider.provider_name,
            provider.model_id,
            int((time.perf_counter() - started) * 1000),
            type(exc).__name__,
        )
        raise
    usage = result.usage
    logger.info(
        "llm_succeeded request_id=%s user_id=%s provider=%s model=%s "
        "duration_ms=%d input_tokens=%d output_tokens=%d total_tokens=%d",
        request.request_id,
        request.user_id,
        result.provider,
        result.model,
        int(result.duration_seconds * 1000),
        usage.input_tokens,
        usage.output_tokens,
        usage.total_tokens,
    )
    return result


def audit_user_id(user: DjangoAuthMe) -> str:
    if user.id != "":
        return user.id
    if user.data.id != "":
        return user.data.id
    return "unknown"
