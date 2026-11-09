import logging

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer

from app.api.dependencies import get_current_django_user
from app.schemas.assistant import ChatRequest, ChatResponse


logger = logging.getLogger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
    dependencies=[Depends(_bearer_scheme), Depends(get_current_django_user)],
)


@router.post("/chat/", response_model=ChatResponse)
async def chat(
    _payload: ChatRequest,
) -> ChatResponse:
    logger.info("user is authenticated")
    return ChatResponse(status="user is authenticated")
