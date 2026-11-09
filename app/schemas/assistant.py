from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=128)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("message must contain non-whitespace characters")
        return value


class ChatResponse(BaseModel):
    status: str
