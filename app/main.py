from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from typing import cast

from fastapi import FastAPI

from app.api.routes.assistant import router as assistant_router
from app.api.routes.health import router as health_router
from app.clients.django import DjangoClient
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_id import RequestIDMiddleware


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    client = cast(DjangoClient | None, getattr(application.state, "django_client", None))
    if client is None:
        client = DjangoClient(
            str(settings.django_api_base_url),
            timeout_seconds=settings.django_timeout_seconds,
            max_response_bytes=settings.django_max_response_bytes,
        )
    application.state.django_client = client
    logging.getLogger(__name__).info("Application started", extra={"environment": settings.environment})
    try:
        yield
    finally:
        await client.aclose()


def create_app() -> FastAPI:
    application = FastAPI(title="Market Data AI Service", lifespan=lifespan)
    application.add_middleware(RequestIDMiddleware)
    application.include_router(health_router)
    application.include_router(assistant_router, prefix="/api/v1")
    return application


app = create_app()
