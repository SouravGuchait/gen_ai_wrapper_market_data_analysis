from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.llm.schemas import TokenUsage


class LLMTestRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("message must contain non-whitespace characters")
        return value


class LLMTestData(BaseModel):
    response: str
    provider: str
    model: str
    finish_reason: str = ""
    usage: TokenUsage
    request_id: str = ""
    duration_seconds: float


class LLMTestEnvelope(BaseModel):
    success: bool
    data: LLMTestData | None = None
    errors: list[str] = Field(default_factory=list)
