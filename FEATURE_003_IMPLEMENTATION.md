# Feature 003 implementation

Verified on 2026-11-20. The OpenAI SDK is mocked in the standard suite. No live xAI or OpenRouter call was made.

## Request flow

1. `POST /api/v1/llm/test` requires a Django Bearer token.
2. `get_current_django_user` calls Django `GET /api/v1/auth/me/`.
3. `get_llm_provider` builds one `OpenAICompatibleProvider` from settings and stores it on the app.
4. `get_llm_rate_limiter` enforces an in-process per-user window. The user key is the `id` from `/api/v1/auth/me/`, including an id nested under `data`.
5. `run_llm_test` calls the provider with a fixed system message and the user message.
6. The provider uses the official async OpenAI client against the selected base URL.
7. Transient provider failures retry up to `LLM_MAX_RETRIES`. Authentication and validation failures do not retry.
8. The route returns the normalized envelope. `handle_llm_error` maps provider failures to that same envelope without SDK text.

## Functions

| Function | Behavior |
| --- | --- |
| `Settings.normalize_llm_provider` | Trims and lowercases `LLM_PROVIDER`. An unknown name does not stop the process from starting. |
| `create_llm_provider` | Builds the OpenAI client and provider for `xai` or `openrouter`. |
| `provider_config` | Selects that provider's key, base URL, and optional OpenRouter headers. |
| `_require_model_id` / `_require_base_url` | Rejects a blank model, a model with whitespace, and a non-HTTP base URL. |
| `OpenAICompatibleProvider.generate` | Sends system and user messages and returns `LLMResponse`. |
| `OpenAICompatibleProvider._call_with_retry` | Retries only `TransientLLMError`. |
| `OpenAICompatibleProvider._create` | Maps SDK timeouts, connection errors, auth failures, rate limits, and status codes to safe exceptions. SDK messages are discarded. |
| `_response` | Copies text, finish reason, provider request id, and duration. Missing token counts become `0`. Empty content is an invalid response. |
| `run_llm_test` | Applies the local limit, calls the provider, and logs outcome metadata. |
| `DjangoAuthMe` | Typed `/api/v1/auth/me/` payload. `audit_user_id` reads `id`, then `data.id`. |
| `RateLimiter.allow` | Counts calls per key inside one process. |
| `http_error` | Maps each safe exception type to a status code and a fixed message. |
| `test_llm` | Validates the message, resolves auth, and returns the envelope. |
| `handle_llm_error` | Renders provider failures as `success: false` without the raw exception. |

## Provider selection

| `LLM_PROVIDER` | Key | Base URL | Model | Extra headers |
| --- | --- | --- | --- | --- |
| `xai` | `LLM_API_KEY` | `LLM_BASE_URL` | `LLM_MODEL_ID` | none |
| `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL` | `LLM_MODEL_ID` | `HTTP-Referer`, `X-Title` when configured |

## Error responses

| Condition | Status | `errors[0]` |
| --- | --- | --- |
| Provider name, model, or URL missing or invalid | 503 | LLM provider is not configured |
| Selected provider has no API key | 503 | LLM provider credentials are missing |
| Provider name is not `xai` or `openrouter` | 503 | LLM provider is not supported |
| Provider rejects the key | 502 | LLM provider rejected the credentials |
| Local per-user limit | 429 | Too many LLM requests |
| Provider rate limit | 429 | LLM provider rate limit exceeded |
| Provider timeout | 504 | LLM provider timed out |
| Provider unreachable or 5xx | 503 | LLM provider is unavailable |
| Empty or unusable completion | 502 | LLM provider returned an invalid response |
| Other provider failure | 502 | LLM provider request failed |

Missing or rejected Django tokens still use the existing `401` `detail` response from Feature 002. Invalid JSON bodies still return `422`.
