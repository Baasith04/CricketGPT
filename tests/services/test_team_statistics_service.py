from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from app.services.teams import team_statistics_service as service


MOCK_OVERALL_ROW = (
    10,
    "Mumbai Indians",
    "MI",
    True,
    291,
    155,
    132,
    4,
    0,
    Decimal("53.26"),
    5,
)

MOCK_DETAIL_ROW = (
    10,
    "Mumbai Indians",
    "MI",
    True,
    291,
    155,
    132,
    4,
    0,
    Decimal("53.26"),
    291,
    47598,
    1736,
    33639,
    Decimal("8.49"),
    291,
    46603,
    1776,
    33620,
    Decimal("8.32"),
    5,
    ["2013", "2015", "2017", "2019", "2020/21"],
)


@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_resolve_team_by_id(mock_conn):
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchone.return_value = (10, "Mumbai Indians", "MI", True)

    result = service._resolve_team(10)

    assert result is not None
    assert result["team_id"] == 10
    assert result["team_name"] == "Mumbai Indians"
    assert result["short_code"] == "MI"


@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_resolve_team_by_name(mock_conn):
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = [(1, "Chennai Super Kings", "CSK", True)]

    result = service._resolve_team("CSK")

    assert result is not None
    assert result["team_id"] == 1
    assert result["team_name"] == "Chennai Super Kings"


@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_resolve_team_not_found(mock_conn):
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = []

    assert service._resolve_team("NonExistentTeam") is None


@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_resolve_team_ambiguous(mock_conn):
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = [
        (1, "Team Alpha", "TA", True),
        (2, "Team Beta", "TB", True),
    ]

    with pytest.raises(ValueError, match="Ambiguous team"):
        service._resolve_team("Team")


def test_resolve_team_empty_input():
    with pytest.raises(ValueError, match="cannot be empty"):
        service._resolve_team("")

    with pytest.raises(ValueError, match="cannot be empty"):
        service._resolve_team("   ")

    with pytest.raises(ValueError, match="cannot be empty"):
        service._resolve_team(None)


@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_get_teams_overall_statistics(mock_conn):
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = [MOCK_OVERALL_ROW]

    results = service.get_teams_overall_statistics()

    assert len(results) == 1
    mi = results[0]
    assert mi["team_name"] == "Mumbai Indians"
    assert mi["matches_played"] == 291
    assert mi["wins"] == 155
    assert mi["ties"] == 4
    assert mi["win_percentage"] == 53.26
    assert mi["championship_titles"] == 5


@patch("app.services.teams.team_statistics_service._resolve_team")
@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_get_individual_team_statistics(mock_conn, mock_resolve):
    mock_resolve.return_value = {
        "team_id": 10,
        "team_name": "Mumbai Indians",
        "short_code": "MI",
        "is_active": True,
    }
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchone.return_value = MOCK_DETAIL_ROW

    result = service.get_individual_team_statistics("MI")

    assert result is not None
    assert result["team_name"] == "Mumbai Indians"
    assert result["runs_scored"] == 47598
    assert result["batting_run_rate"] == 8.49
    assert result["runs_conceded"] == 46603
    assert result["bowling_economy"] == 8.32
    assert result["championship_titles"] == 5
    assert len(result["championship_seasons"]) == 5


@patch("app.services.teams.team_statistics_service._resolve_team")
def test_get_individual_team_statistics_not_found(mock_resolve):
    mock_resolve.return_value = None

    assert service.get_individual_team_statistics("Unknown") is None


@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_get_team_championships(mock_conn):
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = [
        ("2024", 1426312, "2024-05-26", 8, "Kolkata Knight Riders"),
    ]

    champs = service.get_team_championships()

    assert len(champs) == 1
    assert champs[0]["season"] == "2024"
    assert champs[0]["winner"] == "Kolkata Knight Riders"


@patch("app.services.teams.team_statistics_service._resolve_team")
@patch("app.services.teams.team_statistics_service.get_db_connection")
def test_get_team_head_to_head_success(mock_conn, mock_resolve):
    mock_resolve.side_effect = [
        {"team_id": 1, "team_name": "Chennai Super Kings", "short_code": "CSK", "is_active": True},
        {"team_id": 10, "team_name": "Mumbai Indians", "short_code": "MI", "is_active": True},
    ]
    mock_cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchone.return_value = (41, 20, 21, 0, 0)

    h2h = service.get_team_head_to_head("CSK", "MI")

    assert h2h["team_one"] == "Chennai Super Kings"
    assert h2h["team_two"] == "Mumbai Indians"
    assert h2h["matches_played"] == 41
    assert h2h["team_one_wins"] == 20
    assert h2h["team_two_wins"] == 21
    assert h2h["ties"] == 0
    assert h2h["no_results"] == 0


@patch("app.services.teams.team_statistics_service._resolve_team")
def test_get_team_head_to_head_same_team(mock_resolve):
    mock_resolve.side_effect = [
        {"team_id": 1, "team_name": "Chennai Super Kings", "short_code": "CSK", "is_active": True},
        {"team_id": 1, "team_name": "Chennai Super Kings", "short_code": "CSK", "is_active": True},
    ]

    with pytest.raises(ValueError, match="two different teams"):
        service.get_team_head_to_head("CSK", "CSK")


@patch("app.services.teams.team_statistics_service._resolve_team")
def test_get_team_head_to_head_missing_team(mock_resolve):
    mock_resolve.side_effect = [
        {"team_id": 1, "team_name": "Chennai Super Kings", "short_code": "CSK", "is_active": True},
        None,
    ]

    with pytest.raises(ValueError, match="not found"):
        service.get_team_head_to_head("CSK", "Unknown")


@patch("app.services.teams.team_statistics_service.get_db_connection")
@patch("app.services.teams.team_statistics_service._resolve_team")
def test_get_team_versus_matches_returns_all_season_matches(mock_resolve, mock_get_conn):
    mock_resolve.side_effect = [
        {"team_id": 1, "team_name": "Chennai Super Kings", "short_code": "CSK", "is_active": True},
        {"team_id": 10, "team_name": "Mumbai Indians", "short_code": "MI", "is_active": True},
    ]

    import datetime
    fake_rows = [
        (
            1426267,
            "2024",
            datetime.date(2024, 4, 14),
            "Wankhede Stadium",
            "Mumbai",
            None,
            "runs",
            None,
            20,
            None,
            "Chennai Super Kings",
            False,
            {"by": {"runs": 20}, "winner": "Chennai Super Kings"},
            "Chennai Super Kings vs Mumbai Indians",
        ),
    ]
    mock_cur = mock_get_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = fake_rows

    result = service.get_team_versus_matches("CSK", "MI", season="2024")

    assert result["team_one"] == "Chennai Super Kings"
    assert result["team_two"] == "Mumbai Indians"
    assert result["season"] == "2024"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["winner"] == "Chennai Super Kings"
    assert result["matches"][0]["victory_margin"] == "20 runs"
    assert result["matches"][0]["venue"] == "Wankhede Stadium"


@patch("app.services.teams.team_statistics_service.get_db_connection")
@patch("app.services.teams.team_statistics_service._resolve_team")
def test_get_team_versus_matches_empty_season(mock_resolve, mock_get_conn):
    mock_resolve.side_effect = [
        {"team_id": 1, "team_name": "Chennai Super Kings", "short_code": "CSK", "is_active": True},
        {"team_id": 10, "team_name": "Mumbai Indians", "short_code": "MI", "is_active": True},
    ]
    mock_cur = mock_get_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cur.fetchall.return_value = []

    result = service.get_team_versus_matches("CSK", "MI", season="2099")
    assert result["matches"] == []


@patch("app.services.teams.team_statistics_service._resolve_team")
def test_get_team_versus_matches_invalid_team(mock_resolve):
    mock_resolve.return_value = None

    with pytest.raises(ValueError, match="not found"):
        service.get_team_versus_matches("InvalidTeam", "MI", season="2024")

