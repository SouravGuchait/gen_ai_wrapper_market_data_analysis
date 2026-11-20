from typing import Protocol

from app.llm.schemas import GenerationConfig, LLMResponse


class LLMProvider(Protocol):
    provider_name: str
    model_id: str

    async def generate(
        self,
        *,
        system_message: str,
        user_message: str,
        config: GenerationConfig,
    ) -> LLMResponse: ...

    async def aclose(self) -> None: ...
