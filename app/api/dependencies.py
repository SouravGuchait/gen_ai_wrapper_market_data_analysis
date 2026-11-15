from fastapi import HTTPException, Request, status
from pydantic import TypeAdapter

from app.clients.django import DjangoAPIError, DjangoClient

_user_payload = TypeAdapter(dict[str, object])
_BEARER_PART_COUNT = 2


def get_django_client(request: Request) -> DjangoClient:
    client = getattr(request.app.state, "django_client", None)
    if not isinstance(client, DjangoClient):
        raise RuntimeError("Django client is not configured")
    return client


async def get_current_django_user(request: Request) -> dict[str, object]:
    parts = request.headers.get("authorization", "").split()
    if len(parts) != _BEARER_PART_COUNT or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client = get_django_client(request)

    try:
        response = await client.request(
            "GET",
            "api/v1/auth/me/",
            headers={"Authorization": f"Bearer {parts[1]}"},
        )
    except DjangoAPIError as exc:
        if exc.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        unavailable = (
            exc.status_code is None or exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        if unavailable or exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify credentials",
        ) from exc

    try:
        user = _user_payload.validate_json(response.content)
        if len(user) == 0:
            raise ValueError("Django returned an empty user payload")
        return user
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service returned an invalid response",
        ) from exc
