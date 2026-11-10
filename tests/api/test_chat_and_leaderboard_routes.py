"""API tests for POST /api/chat and /api/leaderboards/* endpoints."""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.database.connection import DatabaseConnectionError
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_chat_endpoint_success(mock_route, client: TestClient):
    mock_route.return_value = "Mocked IPL answer."

    response = client.post("/api/chat", json={"question": "Who won IPL 2024?"})

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Who won IPL 2024?"
    assert data["answer"] == "Mocked IPL answer."
    mock_route.assert_called_once_with("Who won IPL 2024?")


def test_chat_endpoint_empty_question_rejected(client: TestClient):
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code == 422


def test_chat_endpoint_too_long_question_rejected(client: TestClient):
    response = client.post("/api/chat", json={"question": "a" * 501})
    assert response.status_code == 422


@patch("app.api.routes.chat.route_question")
def test_chat_endpoint_internal_error_sanitized(mock_route, client: TestClient):
    mock_route.side_effect = DatabaseConnectionError("Secret connection string failure")

    response = client.post("/api/chat", json={"question": "Who won IPL 2024?"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to process your question."
    assert "Secret" not in response.text


# ---------------------------------------------------------------------------
# GET /api/leaderboards/*
# ---------------------------------------------------------------------------

@patch("app.api.routes.leaderboards.get_batting_leaderboard")
def test_leaderboards_batting_success(mock_svc, client: TestClient):
    mock_svc.return_value = [{"player_name": "V Kohli", "total_runs": 9336}]

    response = client.get("/api/leaderboards/batting?category=runs&limit=5&min_balls=100")

    assert response.status_code == 200
    assert response.json()[0]["player_name"] == "V Kohli"
    mock_svc.assert_called_once_with(
        category="runs",
        season=None,
        limit=5,
        min_balls=100,
    )


def test_leaderboards_batting_invalid_category(client: TestClient):
    response = client.get("/api/leaderboards/batting?category=invalid_cat")
    assert response.status_code == 422


def test_leaderboards_batting_invalid_limit(client: TestClient):
    response = client.get("/api/leaderboards/batting?limit=101")
    assert response.status_code == 422


@patch("app.api.routes.leaderboards.get_batting_leaderboard")
def test_leaderboards_batting_db_error(mock_svc, client: TestClient):
    mock_svc.side_effect = DatabaseConnectionError("DB down")

    response = client.get("/api/leaderboards/batting")

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve batting leaderboard."


@patch("app.api.routes.leaderboards.get_bowling_leaderboard")
def test_leaderboards_bowling_success(mock_svc, client: TestClient):
    mock_svc.return_value = [{"player_name": "YS Chahal", "wickets": 233}]

    response = client.get("/api/leaderboards/bowling?category=wickets&season=2024&limit=10")

    assert response.status_code == 200
    assert response.json()[0]["wickets"] == 233
    mock_svc.assert_called_once_with(
        category="wickets",
        season="2024",
        limit=10,
        min_balls=0,
    )


@patch("app.api.routes.leaderboards.get_best_bowling_figures")
def test_leaderboards_best_bowling_success(mock_svc, client: TestClient):
    mock_svc.return_value = [{"player_name": "AS Joseph", "wickets": 6, "runs_conceded": 12}]

    response = client.get("/api/leaderboards/best-bowling?limit=3")

    assert response.status_code == 200
    assert response.json()[0]["player_name"] == "AS Joseph"
    mock_svc.assert_called_once_with(season=None, limit=3)

