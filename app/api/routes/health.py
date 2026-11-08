from fastapi import APIRouter, Response
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/", response_model=dict[str, str])
async def root() -> dict[str, str]:
    return {"service": "Market Data AI Service", "health": "/health"}


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness() -> HealthResponse:
    return HealthResponse(status="ready")
