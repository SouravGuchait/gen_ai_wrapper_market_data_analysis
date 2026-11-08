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
Django responses, request validation, and log redaction. The last recorded
run passed all 22 tests; it used mocked Django responses and does not verify a
live Django deployment.

## Run locally

Use Python 3.12 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app
```

The default local port is `8001`. For auto-reload during development, run
`uvicorn app.main:app --reload --port 8001`.

To install the test tools as well, run `python -m pip install -e ".[dev]"`.

The service exposes `GET /health` (`{"status":"ok"}`) and `GET /ready`
(`{"status":"ready"}`). Both currently report the FastAPI process only; no
Django dependency check is performed. Requests receive an `X-Request-ID` if
the caller does not provide one.

Copy `.env.example` to `.env` to configure `DJANGO_API_BASE_URL`,
`DJANGO_TIMEOUT_SECONDS`, `DJANGO_MAX_RESPONSE_BYTES`, `ENVIRONMENT`, and
`LOG_LEVEL`. The Django client boundary is asynchronous and enforces a timeout,
response-size limit, and safe transport errors. Analytics calls are not
implemented because the live Django OpenAPI contract has not been verified.

## Tests

Run `python -m pytest`. Unit tests use mocked HTTP; live-service integration
tests remain disabled until a separate isolated Django test service and its
verified API contract are available. CI runs the unit suite on Python 3.12.
