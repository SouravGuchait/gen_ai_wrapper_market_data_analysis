# Market Data AI Service

A new, independent FastAPI service for an AI assistant that will consume the existing Market Data Intelligence Django backend.

## Repository boundary
This repository owns only the AI service. The Django application remains in its current repository and keeps its own configuration, tests, and CI/CD. This service has its own tests, configuration, and CI. Communication is through authenticated HTTP APIs, not shared Python imports or database models.

## Feature 001 scope
Create the FastAPI foundation, typed environment configuration, health/readiness endpoints, logging, a minimal Django HTTP-client boundary, pytest structure, and CI workflow.

Feature 001 does not implement an in-app LLM provider, Gemini, OpenRouter, OpenCode, Bedrock, chat, LangChain, LangGraph, vector DB, embeddings, RAG, Gradio, MCP, or direct MySQL access. A frontier coding model can be used externally to build the base project.

## Backend context
The supplied Django README describes authenticated, owner-scoped analytics APIs under `/api/v1/analytics/`. Django calculates analytics using its existing Pandas implementation. The AI service must call those APIs and explain their results, not calculate its own figures.

Exact endpoint suffixes and complete response schemas are not included in the supplied README. Verify them from the live Django OpenAPI schema before implementing typed analytics calls.

See `docs/` and `features/FEATURE_001_FASTAPI_FOUNDATION.md`.

## Feature 002: Django authentication boundary

The frontend continues to register, log in, refresh, and log out through
Django. A protected `POST /api/v1/assistant/chat/` endpoint accepts the Django
access token as a Bearer token. FastAPI forwards it to Django's documented
`GET /api/v1/auth/me/` endpoint before processing the request. A successful
verification currently returns and logs `user is authenticated`; this is a
placeholder boundary, not an LLM-powered assistant.

FastAPI does not store or refresh tokens, accept frontend identity claims, or
provide registration/login endpoints. It rejects missing/invalid credentials,
maps upstream failures to safe responses, validates the chat body, and redacts
credentials from its authentication log. Django analytics calls are not part
of this feature: their live OpenAPI contract remains unverified, so no
analytics endpoint or response schema has been assumed. The auth endpoint
listed above comes from the supplied Django API documentation; no live Django
service was contacted for this milestone.

Run the mocked test suite with `python -m pytest`. Feature 002 tests cover
Bearer forwarding, missing/invalid credentials, unavailable or malformed
Django responses, request validation, and log redaction.

## Feature 003: Direct LLM provider integration

`POST /api/v1/llm/test` is a protected development endpoint. It requires the
same Django Bearer token as chat. FastAPI verifies it with `GET /api/v1/auth/me/`
and then calls the configured OpenAI-compatible provider. The request body is
`{"message": "..."}`. The response uses the envelope
`{"success": true, "data": {...}, "errors": []}`.
Omitted provider token counts are stored as `0`.

`LLM_PROVIDER` selects `xai` or `openrouter`. xAI uses `LLM_API_KEY`,
`LLM_BASE_URL`, and `LLM_MODEL_ID`. OpenRouter uses `OPENROUTER_API_KEY`,
`OPENROUTER_BASE_URL`, and the same `LLM_MODEL_ID`. Optional
`OPENROUTER_HTTP_REFERER` and `OPENROUTER_APP_TITLE` are sent only when set.
Changing provider is an environment change, not a code change. Model IDs and
base URLs are not hardcoded.

Provider errors are mapped to safe HTTP responses. Timeouts, rate limits, and
provider outages retry up to `LLM_MAX_RETRIES` (0–2). Authentication and
validation failures are not retried. The endpoint also applies an in-process
per-user limit (`LLM_RATE_LIMIT_REQUESTS` per `LLM_RATE_LIMIT_WINDOW_SECONDS`).
That limit is not shared across processes.

Logs record request ID, Django user id from `/api/v1/auth/me/`, provider,
model, duration, outcome, and token counts when the provider returns them.
They do not record the prompt, API keys, or bearer token. This is service-side
audit context. Django's documented `/api/v1/audit/` API is read-only, so this
feature does not post a new audit event.

The standard suite mocks the OpenAI SDK and Django. It does not call xAI or
OpenRouter. The latest local run passed 65 tests.

## Run locally

Use Python 3.12 on WSL. The project interpreter is `.venv/bin/python`.
FastAPI listens on port `8002` so it does not collide with Django (`8000`),
the Cursor server (`8001`), or Streamlit (`8501`).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]"
python -m app
```

Development configuration lives in `~/.config/env_vars/dev-ai.env`. The service
reads that file when it is present. `.env.example` only lists the variable
names with placeholder values.

With Docker already running in WSL, install the shell shortcuts once:

```bash
./scripts/install_fpi_commands.sh
source ~/.bashrc
```

Then use:

```bash
fpi_up
fpi_restart
fpi_down
```

`fpi_up` starts the API in the background on port `8002`. On the WSL host,
Django is `http://127.0.0.1:8501/`. Inside the container, that same nginx is
`http://host.docker.internal:8501/` because `127.0.0.1` there is the container.
Compose also sets
`DJANGO_API_HOST_HEADER=127.0.0.1` so Django's `ALLOWED_HOSTS` accepts the
request; without that override Django returns `400` for Host
`host.docker.internal`.

The service exposes `GET /health` (`{"status":"ok"}`) and `GET /ready`
(`{"status":"ready"}`). Both currently report the FastAPI process only; no
Django dependency check is performed. Requests receive an `X-Request-ID` if
the caller does not provide one. Containers write rotating application logs to
`/var/log/ai/app.log`. In local development or CI, if that path is not writable, logging falls back to `logs/app.log`.

`~/.config/env_vars/dev-ai.env` configures `DJANGO_API_BASE_URL`,
`DJANGO_TIMEOUT_SECONDS`, `DJANGO_MAX_RESPONSE_BYTES`, `ENVIRONMENT`,
`LOG_LEVEL`, and the LLM provider variables for this machine.
`.env.example` is only a placeholder reference.
The Django client boundary is asynchronous and enforces a timeout,
response-size limit, and safe transport errors. Analytics calls are not
implemented because the live Django OpenAPI contract has not been verified.

## Tests

Run `python -m pytest`. Unit tests use mocked HTTP; live-service integration
tests remain disabled until a separate isolated Django test service and its
verified API contract are available. CI runs the unit suite on Python 3.12.
