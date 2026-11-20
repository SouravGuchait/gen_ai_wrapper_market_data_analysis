import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from app.llm.exceptions import (
    InvalidProviderResponse,
    LLMError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TransientLLMError,
    UnexpectedProviderError,
)
from app.llm.schemas import GenerationConfig, LLMResponse, ProviderConfig, TokenUsage

Sleeper = Callable[[float], Awaitable[None]]
_BACKOFF_BASE_SECONDS = 0.25
_BACKOFF_CAP_SECONDS = 2.0
_BACKOFF_MULTIPLIER = 2
_AUTH_FAILURES = (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)


class OpenAICompatibleProvider:
    """xAI and OpenRouter share one OpenAI-compatible chat client."""

    def __init__(self, config: ProviderConfig, client: AsyncOpenAI, sleeper: Sleeper) -> None:
        self._config: ProviderConfig = config
        self.provider_name: str = config.provider_name
        self.model_id: str = config.model_id
        self.base_url: str = config.base_url
        self.extra_headers: tuple[tuple[str, str], ...] = config.extra_headers
        self._client: AsyncOpenAI = client
        self._sleep: Sleeper = sleeper

    def __repr__(self) -> str:
        return f"OpenAICompatibleProvider(provider={self.provider_name}, model={self.model_id})"

    async def generate(
        self,
        *,
        system_message: str,
        user_message: str,
        config: GenerationConfig,
    ) -> LLMResponse:
        started = asyncio.get_running_loop().time()
        completion = await self._call_with_retry(_messages(system_message, user_message), config)
        elapsed = asyncio.get_running_loop().time() - started
        return _response(self.provider_name, self.model_id, completion, elapsed)

    async def aclose(self) -> None:
        await self._client.close()

    async def _call_with_retry(
        self,
        messages: list[ChatCompletionMessageParam],
        config: GenerationConfig,
    ) -> ChatCompletion:
        attempt = 0
        while True:
            try:
                return await self._create(messages, config)
            except TransientLLMError:
                if attempt >= self._config.max_retries:
                    raise
                delay = _BACKOFF_BASE_SECONDS * (_BACKOFF_MULTIPLIER**attempt)
                delay = min(delay, _BACKOFF_CAP_SECONDS)
                await self._sleep(delay)
                attempt += 1

    async def _create(
        self,
        messages: list[ChatCompletionMessageParam],
        config: GenerationConfig,
    ) -> ChatCompletion:
        try:
            return await self._client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_output_tokens,
                timeout=config.timeout_seconds,
                extra_headers=dict(self.extra_headers),
            )
        except APITimeoutError:
            raise ProviderTimeoutError("LLM provider timed out") from None
        except APIConnectionError:
            raise ProviderUnavailableError("LLM provider is unavailable") from None
        except AuthenticationError:
            raise ProviderAuthenticationError("LLM provider rejected the credentials") from None
        except RateLimitError:
            raise ProviderRateLimitError("LLM provider rate limit exceeded") from None
        except APIStatusError as exc:
            raise _status_error(exc.status_code) from None
        except APIError:
            raise UnexpectedProviderError("LLM provider request failed") from None


def _messages(system_message: str, user_message: str) -> list[ChatCompletionMessageParam]:
    messages: list[ChatCompletionMessageParam] = []
    cleaned_system = system_message.strip()
    if cleaned_system != "":
        system: ChatCompletionSystemMessageParam = {"role": "system", "content": cleaned_system}
        messages.append(system)
    user: ChatCompletionUserMessageParam = {"role": "user", "content": user_message}
    messages.append(user)
    return messages


def _status_error(status_code: int) -> LLMError:
    error: LLMError = UnexpectedProviderError("LLM provider request failed")
    if status_code in _AUTH_FAILURES:
        error = ProviderAuthenticationError("LLM provider rejected the credentials")
    elif status_code == HTTPStatus.TOO_MANY_REQUESTS:
        error = ProviderRateLimitError("LLM provider rate limit exceeded")
    elif status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        error = ProviderUnavailableError("LLM provider is unavailable")
    return error


def _response(provider: str, model: str, completion: ChatCompletion, elapsed: float) -> LLMResponse:
    if len(completion.choices) == 0:
        raise InvalidProviderResponse("LLM provider returned an invalid response")
    choice = completion.choices[0]
    content = choice.message.content
    if content is None or content.strip() == "":
        raise InvalidProviderResponse("LLM provider returned an invalid response")
    finish_reason = str(choice.finish_reason)
    usage = TokenUsage()
    reported = completion.usage
    if reported is not None:
        usage = TokenUsage(
            input_tokens=reported.prompt_tokens,
            output_tokens=reported.completion_tokens,
            total_tokens=reported.total_tokens,
        )
    return LLMResponse(
        text=content,
        provider=provider,
        model=model,
        finish_reason=finish_reason,
        usage=usage,
        request_id=completion.id,
        duration_seconds=round(elapsed, 6),
    )
