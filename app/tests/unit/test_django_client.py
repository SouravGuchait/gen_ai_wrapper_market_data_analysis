import httpx
import pytest
from anyio.from_thread import start_blocking_portal

from app.clients.django import DjangoAPIError, DjangoClient


def test_client_sends_bearer_header_and_returns_response() -> None:
    seen: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(200, json={"ok": True})

    async def exercise() -> None:
        client = DjangoClient("http://django.test/", transport=httpx.MockTransport(handler))
        try:
            response = await client.request("GET", "/api/v1/example/", headers={"Authorization": "Bearer test-token"})
            assert response.json() == {"ok": True}
            assert seen is not None and seen.headers["Authorization"] == "Bearer test-token"
            assert str(seen.url) == "http://django.test/api/v1/example/"
        finally:
            await client.aclose()

    with start_blocking_portal() as portal:
        portal.call(exercise)


def test_client_maps_http_error_without_body_leak() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="private backend detail")

    async def exercise() -> None:
        client = DjangoClient("http://django.test/", transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(DjangoAPIError, match="unsuccessful response") as error:
                await client.request("GET", "resource")
            assert error.value.status_code == 403
            assert "private backend detail" not in str(error.value)
        finally:
            await client.aclose()

    with start_blocking_portal() as portal:
        portal.call(exercise)


def test_client_maps_timeout_and_enforces_response_limit() -> None:
    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=httpx.Request("GET", "http://django.test/"))

    async def too_large(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"12345")

    async def exercise() -> None:
        client = DjangoClient("http://django.test/", transport=httpx.MockTransport(timeout))
        try:
            with pytest.raises(DjangoAPIError, match="timed out"):
                await client.request("GET", "resource")
        finally:
            await client.aclose()

        client = DjangoClient("http://django.test/", max_response_bytes=4, transport=httpx.MockTransport(too_large))
        try:
            with pytest.raises(DjangoAPIError, match="size limit"):
                await client.request("GET", "resource")
        finally:
            await client.aclose()

    with start_blocking_portal() as portal:
        portal.call(exercise)
