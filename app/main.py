from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_id import RequestIDMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("Application started", extra={"environment": settings.environment})
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="Market Data AI Service", lifespan=lifespan)
    application.add_middleware(RequestIDMiddleware)
    application.include_router(health_router)
    return application


app = create_app()
