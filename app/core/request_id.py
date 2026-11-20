from uuid import uuid4

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID_LENGTH = 128


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        supplied_id = request.headers.get(REQUEST_ID_HEADER, "").strip()
        valid_id = (
            supplied_id != ""
            and len(supplied_id) <= _MAX_REQUEST_ID_LENGTH
            and supplied_id.isascii()
            and all(character.isalnum() or character in "-_." for character in supplied_id)
        )
        request_id = str(uuid4())
        if valid_id:
            request_id = supplied_id
        request.state.request_id = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def read_request_id(request: Request) -> str:
    raw_request_id = getattr(request.state, "request_id", "")
    if isinstance(raw_request_id, str):
        return raw_request_id
    return ""
