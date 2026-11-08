import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_django_user
from app.schemas.assistant import ChatRequest, ChatResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    _: dict[str, Any] = Depends(get_current_django_user),
) -> ChatResponse:
    logger.info("user is authenticated")
    return ChatResponse(status="user is authenticated")
