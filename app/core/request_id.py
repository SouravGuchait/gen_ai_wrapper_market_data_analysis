from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        supplied_id = request.headers.get(REQUEST_ID_HEADER, "").strip()
        valid_id = (
            supplied_id
            and len(supplied_id) <= 128
            and supplied_id.isascii()
            and all(character.isalnum() or character in "-_." for character in supplied_id)
        )
        request_id = supplied_id if valid_id else str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
