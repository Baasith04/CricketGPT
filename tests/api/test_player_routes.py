from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.database.connection import DatabaseConnectionError
from app.main import app

MOCK_BATTING_STATS = {
    "player_id": "ba607b88",
    "player_name": "V Kohli",
    "innings": 275,
    "matches": 275,
    "total_runs": 9336,
    "not_outs": 46,
    "batting_average": 40.77,
    "balls_faced": 6926,
    "strike_rate": 134.80,
    "fours": 845,
    "sixes": 317,
    "fifties": 68,
    "hundreds": 9,
    "highest_score": 113,
}

MOCK_BOWLING_STATS = {
    "player_id": "a12e1d51",
    "player_name": "SL Malinga",
    "innings": 122,
    "matches": 122,
    "legal_balls": 2827,
    "overs": 471.2,
    "maidens": 8,
    "runs_conceded": 3366,
    "wickets": 170,
    "economy": 7.14,
    "bowling_average": 19.80,
    "bowling_strike_rate": 16.63,
    "best_bowling": "5/13",
    "best_bowling_figures": "5/13",
    "best_innings_wickets": 5,
}


@pytest.fixture
def client():
    """Create a test client that talks directly to the FastAPI app."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Batting Leaderboard Tests
# ---------------------------------------------------------------------------

@patch("app.api.routes.players.get_batting_leaderboard")
def test_get_batting_leaderboard_success(mock_get_leaderboard, client: TestClient):
    mock_get_leaderboard.return_value = [MOCK_BATTING_STATS]

    response = client.get("/api/players/leaderboard/batting")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["player_id"] == "ba607b88"
    assert data[0]["player_name"] == "V Kohli"
    assert data[0]["total_runs"] == 9336
    mock_get_leaderboard.assert_called_once_with(limit=20)


@patch("app.api.routes.players.get_batting_leaderboard")
def test_get_batting_leaderboard_custom_limit(mock_get_leaderboard, client: TestClient):
    mock_get_leaderboard.return_value = [MOCK_BATTING_STATS]

    response = client.get("/api/players/leaderboard/batting?limit=5")

    assert response.status_code == 200
    mock_get_leaderboard.assert_called_once_with(limit=5)


def test_get_batting_leaderboard_invalid_limit(client: TestClient):
    # Limit < 1
    response = client.get("/api/players/leaderboard/batting?limit=0")
    assert response.status_code == 422

    # Limit > 100
    response = client.get("/api/players/leaderboard/batting?limit=101")
    assert response.status_code == 422

    # Non-integer limit
    response = client.get("/api/players/leaderboard/batting?limit=invalid")
    assert response.status_code == 422


@patch("app.api.routes.players.get_batting_leaderboard")
def test_get_batting_leaderboard_db_error(mock_get_leaderboard, client: TestClient):
    mock_get_leaderboard.side_effect = DatabaseConnectionError("Host unreachable")

    response = client.get("/api/players/leaderboard/batting")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# Bowling Leaderboard Tests
# ---------------------------------------------------------------------------

@patch("app.api.routes.players.get_bowling_leaderboard")
def test_get_bowling_leaderboard_success(mock_get_leaderboard, client: TestClient):
    mock_get_leaderboard.return_value = [MOCK_BOWLING_STATS]

    response = client.get("/api/players/leaderboard/bowling")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["player_id"] == "a12e1d51"
    assert data[0]["player_name"] == "SL Malinga"
    assert data[0]["wickets"] == 170
    assert data[0]["maidens"] == 8
    assert data[0]["best_bowling"] == "5/13"
    mock_get_leaderboard.assert_called_once_with(limit=20)


@patch("app.api.routes.players.get_bowling_leaderboard")
def test_get_bowling_leaderboard_custom_limit(mock_get_leaderboard, client: TestClient):
    mock_get_leaderboard.return_value = [MOCK_BOWLING_STATS]

    response = client.get("/api/players/leaderboard/bowling?limit=15")

    assert response.status_code == 200
    mock_get_leaderboard.assert_called_once_with(limit=15)


def test_get_bowling_leaderboard_invalid_limit(client: TestClient):
    # Limit < 1
    response = client.get("/api/players/leaderboard/bowling?limit=0")
    assert response.status_code == 422

    # Limit > 100
    response = client.get("/api/players/leaderboard/bowling?limit=105")
    assert response.status_code == 422

    # Non-integer limit
    response = client.get("/api/players/leaderboard/bowling?limit=xyz")
    assert response.status_code == 422


@patch("app.api.routes.players.get_bowling_leaderboard")
def test_get_bowling_leaderboard_db_error(mock_get_leaderboard, client: TestClient):
    mock_get_leaderboard.side_effect = DatabaseConnectionError("Host unreachable")

    response = client.get("/api/players/leaderboard/bowling")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# Individual Player Batting Tests
# ---------------------------------------------------------------------------

@patch("app.api.routes.players.get_player_batting_stats")
def test_get_player_batting_stats_success(mock_get_stats, client: TestClient):
    mock_get_stats.return_value = MOCK_BATTING_STATS

    response = client.get("/api/players/ba607b88/batting")

    assert response.status_code == 200
    data = response.json()
    assert data["player_id"] == "ba607b88"
    assert data["player_name"] == "V Kohli"
    assert data["total_runs"] == 9336
    assert data["batting_average"] == 40.77
    assert data["highest_score"] == 113
    mock_get_stats.assert_called_once_with("ba607b88")


@patch("app.api.routes.players.get_player_batting_stats")
def test_get_player_batting_stats_not_found(mock_get_stats, client: TestClient):
    mock_get_stats.return_value = None

    response = client.get("/api/players/nonexistent_player/batting")

    assert response.status_code == 404
    data = response.json()
    assert "no batting statistics" in data["detail"].lower()


@patch("app.api.routes.players.get_player_batting_stats")
def test_get_player_batting_stats_db_error(mock_get_stats, client: TestClient):
    mock_get_stats.side_effect = DatabaseConnectionError("Connection lost")

    response = client.get("/api/players/ba607b88/batting")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# Individual Player Bowling Tests
# ---------------------------------------------------------------------------

@patch("app.api.routes.players.get_player_bowling_stats")
def test_get_player_bowling_stats_success(mock_get_stats, client: TestClient):
    mock_get_stats.return_value = MOCK_BOWLING_STATS

    response = client.get("/api/players/a12e1d51/bowling")

    assert response.status_code == 200
    data = response.json()
    assert data["player_id"] == "a12e1d51"
    assert data["player_name"] == "SL Malinga"
    assert data["wickets"] == 170
    assert data["maidens"] == 8
    assert data["economy"] == 7.14
    assert data["best_bowling"] == "5/13"
    mock_get_stats.assert_called_once_with("a12e1d51")


@patch("app.api.routes.players.get_player_bowling_stats")
def test_get_player_bowling_stats_not_found(mock_get_stats, client: TestClient):
    mock_get_stats.return_value = None

    response = client.get("/api/players/nonexistent_player/bowling")

    assert response.status_code == 404
    data = response.json()
    assert "no bowling statistics" in data["detail"].lower()


@patch("app.api.routes.players.get_player_bowling_stats")
def test_get_player_bowling_stats_db_error(mock_get_stats, client: TestClient):
    mock_get_stats.side_effect = DatabaseConnectionError("Connection lost")

    response = client.get("/api/players/a12e1d51/bowling")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Database service unavailable."

