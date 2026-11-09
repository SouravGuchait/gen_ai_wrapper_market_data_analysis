from unittest.mock import patch

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from app.api.routes.assistant import logger as assistant_logger
from app.clients.django import DjangoClient
from app.main import app


def perform_chat(
    django_response: httpx.Response,
    *,
    token: str | None = "test-access-token",
    body: dict[str, object] | None = None,
) -> tuple[int, str, dict[str, str], httpx.Request | None]:
    seen_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return django_response

    django_client = DjangoClient("http://django.test/", transport=httpx.MockTransport(handler))
    app.state.django_client = django_client
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    try:
        client = TestClient(app)
        with client:
            response : httpx2.Response = client.request(
                "POST",
                "/api/v1/assistant/chat/",
                json=(
                    body
                    if body is not None
                    else {"message": "Explain the last upload", "conversation_id": None}
                ),
                headers=headers,
            )
    finally:
        if hasattr(app.state, "django_client"):
            del app.state.django_client

    return response.status_code, response.text, dict(response.headers), seen_request


def test_chat_forwards_bearer_token_and_returns_authenticated_message() -> None:
    with patch.object(assistant_logger, "info") as log_info:
        status_code, body, _, request = perform_chat(
            httpx.Response(200, json={"id": 21, "username": "alice"})
        )

    assert status_code == 200
    assert body == '{"status":"user is authenticated"}'
    assert request is not None
    assert request.url.path == "/api/v1/auth/me/"
    assert request.headers["Authorization"] == "Bearer test-access-token"
    log_info.assert_called_once_with("user is authenticated")
    assert "test-access-token" not in repr(log_info.call_args)


@pytest.mark.parametrize("status_code", [401, 403])
def test_chat_rejects_django_authentication_failures(status_code: int) -> None:
    actual_status, body, headers, _ = perform_chat(
        httpx.Response(status_code, json={"detail": "private"})
    )

    assert actual_status == 401
    assert headers["www-authenticate"] == "Bearer"
    assert body == '{"detail":"Invalid or expired access token"}'


def test_chat_rejects_missing_token_without_calling_django() -> None:
    status_code, _, headers, request = perform_chat(
        httpx.Response(200, json={"id": 21}), token=None
    )

    assert status_code == 401
    assert headers["www-authenticate"] == "Bearer"
    assert request is None


@pytest.mark.parametrize(
    ("django_response", "expected_status"),
    [
        (httpx.Response(503), 503),
        (httpx.Response(200, text="not-json"), 502),
        (httpx.Response(200, json=["unexpected", "array"]), 502),
        (httpx.Response(200, json={}), 502),
    ],
)
def test_chat_handles_django_unavailability_and_invalid_user_payloads(
    django_response: httpx.Response,
    expected_status: int,
) -> None:
    status_code, _, _, _ = perform_chat(django_response)

    assert status_code == expected_status


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": ""},
        {"message": "  "},
        {"message": "x" * 4001},
        {"message": "hi", "user_id": 10},
    ],
)
def test_chat_validates_request_body(body: dict[str, object]) -> None:
    status_code, _, _, request = perform_chat(httpx.Response(200, json={"id": 21}), body=body)

    assert status_code == 422
    assert request is not None
