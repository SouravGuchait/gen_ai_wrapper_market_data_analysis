import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.assistant import router as assistant_router
from app.api.routes.health import router as health_router
from app.api.routes.llm import router as llm_router
from app.clients.django import DjangoClient
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_id import RequestIDMiddleware
from app.llm.exceptions import LLMError
from app.llm.http import http_error
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.llm import LLMTestEnvelope


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    # Match Django: /var/log/... is for containers; local/CI may lack permission.
    configure_logging(
        settings.log_level,
        settings.log_file_path,
        allow_fallback=settings.environment == "development",
    )
    existing = getattr(application.state, "django_client", None)
    if isinstance(existing, DjangoClient):
        client = existing
    else:
        client = DjangoClient(
            str(settings.django_api_base_url),
            timeout_seconds=settings.django_timeout_seconds,
            max_response_bytes=settings.django_max_response_bytes,
            host_header=settings.django_api_host_header,
        )
    application.state.django_client = client
    logging.getLogger(__name__).info(
        "Application started", extra={"environment": settings.environment}
    )
    try:
        yield
    finally:
        await client.aclose()
        await _close_llm_provider(application)


def create_app() -> FastAPI:
    application = FastAPI(title="Market Data AI Service", lifespan=lifespan)
    application.add_middleware(RequestIDMiddleware)
    application.add_exception_handler(LLMError, handle_llm_error)
    application.include_router(health_router)
    application.include_router(assistant_router, prefix="/api/v1")
    application.include_router(llm_router, prefix="/api/v1")
    return application


async def handle_llm_error(_request: Request, exc: Exception) -> JSONResponse:
    error = LLMError("LLM provider request failed")
    if isinstance(exc, LLMError):
        error = exc
    status_code, message = http_error(error)
    body = LLMTestEnvelope(success=False, errors=[message])
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def _close_llm_provider(application: FastAPI) -> None:
    llm_provider = getattr(application.state, "llm_provider", None)
    if isinstance(llm_provider, OpenAICompatibleProvider):
        await llm_provider.aclose()


app = create_app()
