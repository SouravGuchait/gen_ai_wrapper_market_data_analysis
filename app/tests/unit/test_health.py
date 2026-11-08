from fastapi.testclient import TestClient

from app.main import app


def test_health_and_readiness() -> None:
    with TestClient(app) as client:
        assert client.get("/").json() == {
            "service": "Market Data AI Service",
            "health": "/health",
        }
        assert client.get("/favicon.ico").status_code == 204
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}


def test_request_id_is_preserved_or_created() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "client-request-123"})
        assert response.headers["X-Request-ID"] == "client-request-123"
        generated = client.get("/health").headers["X-Request-ID"]
        assert len(generated) == 36


def test_oversized_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "x" * 129})
        assert len(response.headers["X-Request-ID"]) == 36
