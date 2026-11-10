"""
CricketGPT — Tests for the main FastAPI application

Key concepts:
- pytest discovers any function whose name starts with 'test_'.
- Starlette's TestClient wraps the FastAPI app so we can send HTTP requests
  without starting a real server — tests run instantly in-process.
- Each test sends a request and then uses 'assert' to verify the response.
"""

from starlette.testclient import TestClient

from app.main import app


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
