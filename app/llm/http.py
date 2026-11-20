from app.llm.exceptions import (
    InvalidProviderConfiguration,
    InvalidProviderResponse,
    LLMError,
    LocalRateLimitError,
    MissingCredentials,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnexpectedProviderError,
    UnsupportedProvider,
)

_HTTP_ERRORS: dict[type[LLMError], tuple[int, str]] = {
    InvalidProviderConfiguration: (503, "LLM provider is not configured"),
    MissingCredentials: (503, "LLM provider credentials are missing"),
    UnsupportedProvider: (503, "LLM provider is not supported"),
    ProviderAuthenticationError: (502, "LLM provider rejected the credentials"),
    LocalRateLimitError: (429, "Too many LLM requests"),
    ProviderRateLimitError: (429, "LLM provider rate limit exceeded"),
    ProviderTimeoutError: (504, "LLM provider timed out"),
    ProviderUnavailableError: (503, "LLM provider is unavailable"),
    InvalidProviderResponse: (502, "LLM provider returned an invalid response"),
    UnexpectedProviderError: (502, "LLM provider request failed"),
}


def http_error(error: LLMError) -> tuple[int, str]:
    mapped = _HTTP_ERRORS.get(type(error))
    if mapped is None:
        return (502, "LLM provider request failed")
    return mapped
