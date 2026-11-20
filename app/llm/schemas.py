from dataclasses import dataclass

from pydantic import BaseModel


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    text: str
    provider: str
    model: str
    finish_reason: str = ""
    usage: TokenUsage
    request_id: str = ""
    duration_seconds: float


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class ProviderConfig:
    provider_name: str
    model_id: str
    api_key: str
    base_url: str
    timeout_seconds: float
    max_retries: int
    extra_headers: tuple[tuple[str, str], ...]

    def __repr__(self) -> str:
        return f"ProviderConfig(provider={self.provider_name}, model={self.model_id})"


@dataclass(frozen=True)
class LLMRequest:
    message: str
    config: GenerationConfig
    request_id: str
    user_id: str
