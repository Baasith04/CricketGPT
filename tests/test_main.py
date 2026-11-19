"""
CricketGPT — Tests for the main FastAPI application

Key concepts:
- pytest discovers any function whose name starts with 'test_'.
- Starlette's TestClient wraps the FastAPI app so we can send HTTP requests
  without starting a real server — tests run instantly in-process.
- Each test sends a request and then uses 'assert' to verify the response.
"""

from starlette.testclient import TestClient

from app.main import app, build_cors_config, create_app, parse_cors_origins


# ---------------------------------------------------------------------------
# Shared test client fixture
# ---------------------------------------------------------------------------
# A pytest "fixture" is a reusable setup function.
# Tests can request the fixture by including its name as a parameter.
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture
def client():
    """Create an HTTP test client that talks directly to our FastAPI app."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_root_returns_welcome_message(client: TestClient):
    """GET / should return a welcome message and project name."""
    response = client.get("/")

    # Status code 200 means success
    assert response.status_code == 200

    data = response.json()
    assert data["project"] == "CricketGPT"
    assert "Welcome" in data["message"]


def test_health_check_returns_healthy(client: TestClient):
    """GET /health should report the service as healthy."""
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CricketGPT"


def test_app_info_returns_correct_metadata(client: TestClient):
    """GET /api/info should return name, version and environment."""
    response = client.get("/api/info")

    assert response.status_code == 200

    data = response.json()
    assert data["app_name"] == "CricketGPT"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"
    assert len(data["description"]) > 0


def test_cors_allows_unconfigured_api_usage(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "")
    cfg = build_cors_config()
    assert cfg["allow_origins"] == []
    assert cfg["allow_credentials"] is False

    test_app = create_app()
    with TestClient(test_app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200
        assert "access-control-allow-origin" not in resp.headers


def test_cors_supports_comma_separated_origins_and_blocks_wildcard_credentials(monkeypatch):
    origins = parse_cors_origins("https://app.cricketgpt.in, https://preview.cricketgpt.in ")
    assert origins == ["https://app.cricketgpt.in", "https://preview.cricketgpt.in"]

    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.cricketgpt.in, https://preview.cricketgpt.in")
    cfg = build_cors_config()
    assert cfg["allow_credentials"] is True

    test_app = create_app()
    with TestClient(test_app) as c:
        resp = c.get("/health", headers={"Origin": "https://preview.cricketgpt.in"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://preview.cricketgpt.in"
        assert resp.headers.get("access-control-allow-credentials") == "true"

    wildcard_cfg = build_cors_config("*")
    assert wildcard_cfg["allow_origins"] == ["*"]
    assert wildcard_cfg["allow_credentials"] is False
