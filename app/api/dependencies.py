import logging

from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.clients.django import DjangoAPIError, DjangoClient
from app.core.config import get_settings
from app.core.request_id import read_request_id
from app.llm.exceptions import LLMError
from app.llm.factory import create_llm_provider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.rate_limit import RateLimiter
from app.schemas.django_user import DjangoAuthMe

logger = logging.getLogger(__name__)

_BEARER_PART_COUNT = 2


def get_django_client(request: Request) -> DjangoClient:
    client = getattr(request.app.state, "django_client", None)
    if not isinstance(client, DjangoClient):
        raise RuntimeError("Django client is not configured")
    return client


async def get_current_django_user(request: Request) -> DjangoAuthMe:
    parts = request.headers.get("authorization", "").split()
    if len(parts) != _BEARER_PART_COUNT or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client = get_django_client(request)

    try:
        response = await client.request(
            "GET",
            "api/v1/auth/me/",
            headers={"Authorization": f"Bearer {parts[1]}"},
        )
    except DjangoAPIError as exc:
        if exc.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        unavailable = (
            exc.status_code is None or exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        if unavailable or exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify credentials",
        ) from exc

    try:
        return DjangoAuthMe.model_validate_json(response.content)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service returned an invalid response",
        ) from exc


def get_llm_provider(request: Request) -> OpenAICompatibleProvider:
    current = getattr(request.app.state, "llm_provider", None)
    if isinstance(current, OpenAICompatibleProvider):
        return current
    try:
        provider = create_llm_provider(get_settings())
    except LLMError as exc:
        logger.info(
            "llm_rejected request_id=%s error=%s",
            read_request_id(request),
            type(exc).__name__,
        )
        raise
    request.app.state.llm_provider = provider
    return provider


def get_llm_rate_limiter(request: Request) -> RateLimiter:
    current = getattr(request.app.state, "llm_rate_limiter", None)
    if isinstance(current, RateLimiter):
        return current
    settings = get_settings()
    limiter = RateLimiter(
        settings.llm_rate_limit_requests,
        settings.llm_rate_limit_window_seconds,
    )
    request.app.state.llm_rate_limiter = limiter
    return limiter
