from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.database.connection import DatabaseConnectionError
from app.main import app

MOCK_TEAM_OVERALL = {
    "team_id": 10,
    "team_name": "Mumbai Indians",
    "short_code": "MI",
    "is_active": True,
    "matches_played": 291,
    "wins": 155,
    "losses": 132,
    "ties": 4,
    "no_results": 0,
    "win_percentage": 53.26,
    "championship_titles": 5,
}

MOCK_TEAM_DETAIL = {
    "team_id": 10,
    "team_name": "Mumbai Indians",
    "short_code": "MI",
    "is_active": True,
    "matches_played": 291,
    "wins": 155,
    "losses": 132,
    "ties": 4,
    "no_results": 0,
    "win_percentage": 53.26,
    "innings_batted": 291,
    "runs_scored": 47598,
    "wickets_lost": 1736,
    "legal_balls_faced": 33639,
    "batting_run_rate": 8.49,
    "innings_bowled": 291,
    "runs_conceded": 46603,
    "wickets_taken": 1776,
    "legal_balls_bowled": 33620,
    "bowling_economy": 8.32,
    "championship_titles": 5,
    "championship_seasons": ["2013", "2015", "2017", "2019", "2020/21"],
}

MOCK_CHAMPIONSHIP = {
    "season": "2024",
    "match_id": 1426312,
    "match_date": "2024-05-26",
    "team_id": 8,
    "winner": "Kolkata Knight Riders",
}

MOCK_HEAD_TO_HEAD = {
    "team_one": "Chennai Super Kings",
    "team_two": "Mumbai Indians",
    "matches_played": 41,
    "team_one_wins": 20,
    "team_two_wins": 21,
    "ties": 0,
    "no_results": 0,
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Teams Overall Statistics Endpoints
# ---------------------------------------------------------------------------

@patch("app.api.routes.teams.get_teams_overall_statistics")
def test_teams_overall_statistics_success(mock_service, client: TestClient):
    mock_service.return_value = [MOCK_TEAM_OVERALL]

    response = client.get("/api/teams")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["team_name"] == "Mumbai Indians"
    assert data[0]["wins"] == 155
    assert data[0]["win_percentage"] == 53.26
    mock_service.assert_called_once_with(active_only=False)


@patch("app.api.routes.teams.get_teams_overall_statistics")
def test_teams_overall_statistics_active_only(mock_service, client: TestClient):
    mock_service.return_value = [MOCK_TEAM_OVERALL]

    response = client.get("/api/teams?active_only=true")

    assert response.status_code == 200
    mock_service.assert_called_once_with(active_only=True)


@patch("app.api.routes.teams.get_teams_overall_statistics")
def test_teams_overall_statistics_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("DB connection failed")

    response = client.get("/api/teams")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# Championship Titles Endpoints
# ---------------------------------------------------------------------------

@patch("app.api.routes.teams.get_team_championships")
def test_team_championships_success(mock_service, client: TestClient):
    mock_service.return_value = [MOCK_CHAMPIONSHIP]

    response = client.get("/api/teams/championships")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["season"] == "2024"
    assert data[0]["winner"] == "Kolkata Knight Riders"


@patch("app.api.routes.teams.get_team_championships")
def test_team_championships_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("DB error")

    response = client.get("/api/teams/championships")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# Head-to-Head Statistics Endpoints
# ---------------------------------------------------------------------------

@patch("app.api.routes.teams.get_team_head_to_head")
def test_team_head_to_head_success(mock_service, client: TestClient):
    mock_service.return_value = MOCK_HEAD_TO_HEAD

    response = client.get("/api/teams/head-to-head?team_one=CSK&team_two=MI")

    assert response.status_code == 200
    data = response.json()
    assert data["team_one"] == "Chennai Super Kings"
    assert data["team_two"] == "Mumbai Indians"
    assert data["matches_played"] == 41
    assert data["team_one_wins"] == 20
    assert data["team_two_wins"] == 21
    mock_service.assert_called_once_with("CSK", "MI")


def test_team_head_to_head_missing_parameters(client: TestClient):
    response = client.get("/api/teams/head-to-head?team_one=CSK")
    assert response.status_code == 422


@patch("app.api.routes.teams.get_team_head_to_head")
def test_team_head_to_head_same_team(mock_service, client: TestClient):
    mock_service.side_effect = ValueError("Please provide two different teams.")

    response = client.get("/api/teams/head-to-head?team_one=CSK&team_two=CSK")

    assert response.status_code == 400
    assert "different teams" in response.json()["detail"]


@patch("app.api.routes.teams.get_team_head_to_head")
def test_team_head_to_head_team_not_found(mock_service, client: TestClient):
    mock_service.side_effect = ValueError("Team 'Unknown' was not found.")

    response = client.get("/api/teams/head-to-head?team_one=CSK&team_two=Unknown")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@patch("app.api.routes.teams.get_team_head_to_head")
def test_team_head_to_head_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("DB failure")

    response = client.get("/api/teams/head-to-head?team_one=CSK&team_two=MI")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# Individual Team Statistics Endpoints
# ---------------------------------------------------------------------------

@patch("app.api.routes.teams.get_individual_team_statistics")
def test_individual_team_statistics_success(mock_service, client: TestClient):
    mock_service.return_value = MOCK_TEAM_DETAIL

    response = client.get("/api/teams/10")

    assert response.status_code == 200
    data = response.json()
    assert data["team_name"] == "Mumbai Indians"
    assert data["runs_scored"] == 47598
    assert data["championship_titles"] == 5
    mock_service.assert_called_once_with("10")


@patch("app.api.routes.teams.get_individual_team_statistics")
def test_individual_team_statistics_subpath(mock_service, client: TestClient):
    mock_service.return_value = MOCK_TEAM_DETAIL

    response = client.get("/api/teams/MI/statistics")

    assert response.status_code == 200
    data = response.json()
    assert data["team_name"] == "Mumbai Indians"
    mock_service.assert_called_once_with("MI")


@patch("app.api.routes.teams.get_individual_team_statistics")
def test_individual_team_statistics_not_found(mock_service, client: TestClient):
    mock_service.return_value = None

    response = client.get("/api/teams/NonExistentTeam")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@patch("app.api.routes.teams.get_individual_team_statistics")
def test_individual_team_statistics_ambiguous(mock_service, client: TestClient):
    mock_service.side_effect = ValueError("Ambiguous team 'Team'.")

    response = client.get("/api/teams/Team")

    assert response.status_code == 400
    assert "Ambiguous team" in response.json()["detail"]


@patch("app.api.routes.teams.get_individual_team_statistics")
def test_individual_team_statistics_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("Database offline")

    response = client.get("/api/teams/CSK")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."

