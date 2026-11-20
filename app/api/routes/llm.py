from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer

from app.api.dependencies import get_current_django_user, get_llm_provider, get_llm_rate_limiter
from app.core.config import get_settings
from app.core.request_id import read_request_id
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.rate_limit import RateLimiter
from app.llm.schemas import GenerationConfig, LLMRequest
from app.schemas.django_user import DjangoAuthMe
from app.schemas.llm import LLMTestData, LLMTestEnvelope, LLMTestRequest
from app.services.llm_service import audit_user_id, run_llm_test

_bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/llm",
    tags=["llm"],
    dependencies=[Depends(_bearer_scheme)],
)


@router.post("/test", response_model=LLMTestEnvelope)
async def test_llm(
    payload: LLMTestRequest,
    request: Request,
    user: Annotated[DjangoAuthMe, Depends(get_current_django_user)],
    provider: Annotated[OpenAICompatibleProvider, Depends(get_llm_provider)],
    limiter: Annotated[RateLimiter, Depends(get_llm_rate_limiter)],
) -> LLMTestEnvelope:
    settings = get_settings()
    result = await run_llm_test(
        provider,
        limiter,
        LLMRequest(
            message=payload.message,
            config=GenerationConfig(
                temperature=settings.llm_temperature,
                max_output_tokens=settings.llm_max_output_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
            ),
            request_id=read_request_id(request),
            user_id=audit_user_id(user),
        ),
    )
    return LLMTestEnvelope(
        success=True,
        data=LLMTestData(
            response=result.text,
            provider=result.provider,
            model=result.model,
            finish_reason=result.finish_reason,
            usage=result.usage,
            request_id=result.request_id,
            duration_seconds=result.duration_seconds,
        ),
    )
