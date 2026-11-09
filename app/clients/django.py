from collections.abc import Mapping
import httpx


class DjangoAPIError(Exception):
    """A safe, transport-level error communicating with Django."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code: int | None = status_code


class DjangoClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 1_048_576,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            follow_redirects=False,
        )
        self._max_response_bytes: int = max_response_bytes

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        try:
            async with self._client.stream(
                method, path.lstrip("/"), headers=headers, params=params, json=json
            ) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        raise DjangoAPIError(
                            "Django response exceeded configured size limit", status_code=response.status_code
                        )
                response = httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=bytes(body),
                    request=response.request,
                )
                if response.is_error:
                    raise DjangoAPIError(
                        "Django returned an unsuccessful response", status_code=response.status_code
                    )
                return response
        except httpx.TimeoutException as exc:
            raise DjangoAPIError("Django request timed out") from exc
        except httpx.RequestError as exc:
            raise DjangoAPIError("Django request failed") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
