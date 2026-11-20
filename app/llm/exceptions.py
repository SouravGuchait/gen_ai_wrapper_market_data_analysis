class LLMError(Exception):
    """Safe provider failure. The message must never include credentials."""


class InvalidProviderConfiguration(LLMError):
    """The selected provider is missing a required non-secret setting."""


class MissingCredentials(LLMError):
    """The selected provider has no API key configured."""


class UnsupportedProvider(LLMError):
    """LLM_PROVIDER is not one of the configured providers."""


class TransientLLMError(LLMError):
    """A failure that may succeed on a later attempt."""


class ProviderAuthenticationError(LLMError):
    """The provider rejected the configured credentials."""


class ProviderRateLimitError(TransientLLMError):
    """The provider asked the client to slow down."""


class ProviderTimeoutError(TransientLLMError):
    """The provider did not answer before the configured timeout."""


class ProviderUnavailableError(TransientLLMError):
    """The provider could not be reached or returned a server error."""


class InvalidProviderResponse(LLMError):
    """The provider response could not be normalized."""


class UnexpectedProviderError(LLMError):
    """The provider failed in a way that should not be retried."""


class LocalRateLimitError(LLMError):
    """This service rejected the call before contacting the provider."""
