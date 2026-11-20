import asyncio

from openai import AsyncOpenAI

from app.core.config import Settings
from app.llm.exceptions import InvalidProviderConfiguration, MissingCredentials, UnsupportedProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.schemas import ProviderConfig

_MAX_MODEL_ID_LENGTH = 256
_HTTP_PREFIXES = ("https://", "http://")


def create_llm_provider(settings: Settings) -> OpenAICompatibleProvider:
    config = provider_config(settings)
    client = AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=0,
    )
    return OpenAICompatibleProvider(config, client, asyncio.sleep)


def provider_config(settings: Settings) -> ProviderConfig:
    provider_name = settings.llm_provider
    api_key = ""
    base_url = ""
    headers: tuple[tuple[str, str], ...] = ()
    if provider_name == "xai":
        api_key = settings.llm_api_key.get_secret_value()
        base_url = settings.llm_base_url
    elif provider_name == "openrouter":
        api_key = settings.openrouter_api_key.get_secret_value()
        base_url = settings.openrouter_base_url
        headers = _openrouter_headers(settings)
    elif provider_name == "":
        raise InvalidProviderConfiguration("LLM provider is not configured")
    else:
        raise UnsupportedProvider("LLM provider is not supported")
    cleaned_key = api_key.strip()
    if cleaned_key == "":
        raise MissingCredentials("LLM provider credentials are missing")
    return ProviderConfig(
        provider_name=provider_name,
        model_id=_require_model_id(settings.llm_model_id),
        api_key=cleaned_key,
        base_url=_require_base_url(base_url),
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        extra_headers=headers,
    )


def _openrouter_headers(settings: Settings) -> tuple[tuple[str, str], ...]:
    headers: list[tuple[str, str]] = []
    referer = settings.openrouter_http_referer.strip()
    title = settings.openrouter_app_title.strip()
    if referer != "":
        headers.append(("HTTP-Referer", referer))
    if title != "":
        headers.append(("X-Title", title))
    return tuple(headers)


def _require_model_id(value: str) -> str:
    cleaned = value.strip()
    if (
        cleaned == ""
        or len(cleaned) > _MAX_MODEL_ID_LENGTH
        or any(char.isspace() for char in cleaned)
    ):
        raise InvalidProviderConfiguration("LLM model is not configured")
    return cleaned


def _require_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if cleaned.startswith(_HTTP_PREFIXES):
        return cleaned
    raise InvalidProviderConfiguration("LLM base URL is not configured")
