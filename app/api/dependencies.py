from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, TypeAdapter, ValidationError

from app.clients.django import DjangoAPIError, DjangoClient

_bearer_scheme = HTTPBearer(auto_error=False)
_user_payload = TypeAdapter(Annotated[dict[str, Any], Field(min_length=1)])


def get_django_client(request: Request) -> DjangoClient:
    return request.app.state.django_client


async def get_current_django_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    client: DjangoClient = Depends(get_django_client),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = await client.request(
            "GET",
            "api/v1/auth/me/",
            headers={"Authorization": f"Bearer {credentials.credentials}"},
        )
    except DjangoAPIError as exc:
        if exc.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if exc.status_code is None or exc.status_code >= 500 or exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify credentials",
        ) from exc

    try:
        return _user_payload.validate_python(response.json())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service returned an invalid response",
        ) from exc
