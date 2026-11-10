from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.database.connection import DatabaseConnectionError
from app.main import app

MOCK_MATCH_DETAIL = {
    "match_id": 335982,
    "season": "2007/08",
    "match_date": "2008-04-18",
    "venue": "M Chinnaswamy Stadium, Bangalore",
    "city": "Bangalore",
    "stage": None,
    "teams": [
        {
            "team_id": 14,
            "team_name": "Royal Challengers Bengaluru",
            "short_code": "RCB",
            "team_number": 1,
            "original_team_name": "Royal Challengers Bangalore",
        },
        {
            "team_id": 8,
            "team_name": "Kolkata Knight Riders",
            "short_code": "KKR",
            "team_number": 2,
            "original_team_name": "Kolkata Knight Riders",
        },
    ],
    "toss": {
        "toss_winner_id": 14,
        "toss_winner_name": "Royal Challengers Bengaluru",
        "toss_decision": "field",
    },
    "result": {
        "result_type": "runs",
        "result_method": None,
        "winner_id": 8,
        "winner_name": "Kolkata Knight Riders",
        "win_by_runs": 140,
        "win_by_wickets": None,
        "is_super_over": False,
        "summary": "Kolkata Knight Riders won by 140 runs",
    },
}

MOCK_SCORECARD = {
    "match": MOCK_MATCH_DETAIL,
    "has_super_over": False,
    "innings": [
        {
            "innings_id": 1,
            "innings_number": 1,
            "batting_team_id": 8,
            "batting_team": "Kolkata Knight Riders",
            "bowling_team_id": 14,
            "bowling_team": "Royal Challengers Bengaluru",
            "total_runs": 222,
            "total_wickets": 3,
            "legal_balls_bowled": 120,
            "overs": "20.0",
            "run_rate": 11.1,
            "is_super_over": False,
            "target_runs": None,
            "batting": [
                {
                    "player_id": "b8a55852",
                    "player_name": "BB McCullum",
                    "runs": 158,
                    "balls": 73,
                    "fours": 10,
                    "sixes": 13,
                    "strike_rate": 216.44,
                    "is_out": False,
                    "dismissal": "not out",
                }
            ],
            "bowling": [
                {
                    "player_id": "91a4a398",
                    "player_name": "Z Khan",
                    "overs": "4.0",
                    "legal_balls": 24,
                    "maidens": 0,
                    "runs_conceded": 38,
                    "wickets": 1,
                    "economy": 9.5,
                    "wides": 2,
                    "no_balls": 0,
                }
            ],
            "extras": {
                "wides": 9,
                "no_balls": 0,
                "byes": 4,
                "leg_byes": 4,
                "penalty": 0,
                "total_extras": 17,
            },
        }
    ],
    "super_overs": [],
}

MOCK_WICKETS = {
    "match_id": 335982,
    "has_super_over": False,
    "innings": [
        {
            "innings_id": 1,
            "innings_number": 1,
            "batting_team_id": 8,
            "batting_team": "Kolkata Knight Riders",
            "is_super_over": False,
            "total_runs": 222,
            "total_wickets": 3,
            "fall_of_wickets": [
                {
                    "wicket_number": 1,
                    "player_id": "725529bc",
                    "player_name": "SC Ganguly",
                    "dismissal_kind": "caught",
                    "bowler_id": "91a4a398",
                    "bowler_name": "Z Khan",
                    "fielders": ["JH Kallis"],
                    "score": 61,
                    "overs": "5.2",
                    "over_number": 5,
                    "delivery_sequence": 2,
                }
            ],
        }
    ],
    "super_overs": [],
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/matches/{match_id}
# ---------------------------------------------------------------------------

@patch("app.api.routes.matches.get_match_details")
def test_get_match_details_success(mock_service, client: TestClient):
    mock_service.return_value = MOCK_MATCH_DETAIL

    response = client.get("/api/matches/335982")

    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == 335982
    assert data["season"] == "2007/08"
    assert len(data["teams"]) == 2
    assert data["result"]["winner_name"] == "Kolkata Knight Riders"
    mock_service.assert_called_once_with(335982)


@patch("app.api.routes.matches.get_match_details")
def test_get_match_details_not_found(mock_service, client: TestClient):
    mock_service.return_value = None

    response = client.get("/api/matches/999999")

    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_get_match_details_invalid_id(client: TestClient):
    response = client.get("/api/matches/0")
    assert response.status_code == 422

    response = client.get("/api/matches/not-a-number")
    assert response.status_code == 422


@patch("app.api.routes.matches.get_match_details")
def test_get_match_details_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("DB down")

    response = client.get("/api/matches/335982")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# GET /api/matches/{match_id}/scorecard
# ---------------------------------------------------------------------------

@patch("app.api.routes.matches.get_match_scorecard")
def test_get_match_scorecard_success(mock_service, client: TestClient):
    mock_service.return_value = MOCK_SCORECARD

    response = client.get("/api/matches/335982/scorecard")

    assert response.status_code == 200
    data = response.json()
    assert data["match"]["match_id"] == 335982
    assert data["has_super_over"] is False
    assert len(data["innings"]) == 1
    assert data["innings"][0]["total_runs"] == 222
    assert data["innings"][0]["batting"][0]["player_name"] == "BB McCullum"
    assert data["innings"][0]["bowling"][0]["player_name"] == "Z Khan"
    assert data["innings"][0]["extras"]["total_extras"] == 17
    mock_service.assert_called_once_with(335982)


@patch("app.api.routes.matches.get_match_scorecard")
def test_get_match_scorecard_not_found(mock_service, client: TestClient):
    mock_service.return_value = None

    response = client.get("/api/matches/999999/scorecard")

    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_get_match_scorecard_invalid_id(client: TestClient):
    response = client.get("/api/matches/-1/scorecard")
    assert response.status_code == 422


@patch("app.api.routes.matches.get_match_scorecard")
def test_get_match_scorecard_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("DB down")

    response = client.get("/api/matches/335982/scorecard")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."


# ---------------------------------------------------------------------------
# GET /api/matches/{match_id}/wickets
# ---------------------------------------------------------------------------

@patch("app.api.routes.matches.get_match_wickets")
def test_get_match_wickets_success(mock_service, client: TestClient):
    mock_service.return_value = MOCK_WICKETS

    response = client.get("/api/matches/335982/wickets")

    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == 335982
    assert len(data["innings"]) == 1
    assert data["innings"][0]["fall_of_wickets"][0]["player_name"] == "SC Ganguly"
    assert data["innings"][0]["fall_of_wickets"][0]["score"] == 61
    assert data["innings"][0]["fall_of_wickets"][0]["overs"] == "5.2"
    mock_service.assert_called_once_with(335982)


@patch("app.api.routes.matches.get_match_wickets")
def test_get_match_wickets_not_found(mock_service, client: TestClient):
    mock_service.return_value = None

    response = client.get("/api/matches/999999/wickets")

    assert response.status_code == 404


def test_get_match_wickets_invalid_id(client: TestClient):
    response = client.get("/api/matches/0/wickets")
    assert response.status_code == 422


@patch("app.api.routes.matches.get_match_wickets")
def test_get_match_wickets_db_error(mock_service, client: TestClient):
    mock_service.side_effect = DatabaseConnectionError("DB down")

    response = client.get("/api/matches/335982/wickets")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database service unavailable."

