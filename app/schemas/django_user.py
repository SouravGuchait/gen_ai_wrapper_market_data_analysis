from typing import Annotated, ClassVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def coerce_user_id(value: object) -> str:
    cleaned = ""
    if isinstance(value, int) and not isinstance(value, bool):
        cleaned = str(value)
    elif isinstance(value, str):
        cleaned = value.strip()
    return cleaned


UserId = Annotated[str, BeforeValidator(coerce_user_id)]


class DjangoUserData(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    id: UserId = ""


class DjangoAuthMe(BaseModel):
    """User payload from Django GET /api/v1/auth/me/."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    id: UserId = ""
    data: DjangoUserData = Field(default_factory=DjangoUserData)

    @model_validator(mode="before")
    @classmethod
    def reject_empty_payload(cls, value: object) -> object:
        if isinstance(value, dict) and len(value) > 0:
            return value
        raise ValueError("Django returned an empty user payload")
