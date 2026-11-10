from decimal import Decimal
from unittest.mock import patch
import pytest

from app.services.statistics.bowling_service import (
    get_bowling_leaderboard,
    get_player_bowling_stats,
)

MALINGA_ROW = (
    "a12e1d51",
    "SL Malinga",
    122,
    122,
    2827,
    Decimal("471.2"),
    8,
    3366,
    170,
    Decimal("7.14"),
    Decimal("19.80"),
    Decimal("16.63"),
    "5/13",
)

BHUVI_ROW = (
    "2e81a32d",
    "B Kumar",
    206,
    206,
    4600,
    Decimal("766.7"),
    14,
    5913,
    226,
    Decimal("7.71"),
    Decimal("26.16"),
    Decimal("20.35"),
    "5/19",
)

ZERO_WICKET_ROW = (
    "test_zero",
    "Zero Wicket Bowler",
    2,
    2,
    36,
    Decimal("6.0"),
    0,
    50,
    0,
    Decimal("8.33"),
    None,
    None,
    "0/20",
)


@patch("app.services.statistics.bowling_service.get_db_connection")
def test_get_player_bowling_stats(mock_connection):
    mock_cursor = (
        mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    )
    mock_cursor.fetchone.return_value = MALINGA_ROW

    result = get_player_bowling_stats("a12e1d51")

    assert result is not None
    assert result["player_id"] == "a12e1d51"
    assert result["player_name"] == "SL Malinga"
    assert result["innings"] == 122
    assert result["matches"] == 122
    assert result["legal_balls"] == 2827
    assert result["overs"] == 471.2
    assert result["maidens"] == 8
    assert result["runs_conceded"] == 3366
    assert result["wickets"] == 170
    assert result["economy"] == 7.14
    assert result["bowling_average"] == 19.80
    assert result["bowling_strike_rate"] == 16.63
    assert result["best_bowling"] == "5/13"
    assert result["best_bowling_figures"] == "5/13"
    assert result["best_innings_wickets"] == 5


@patch("app.services.statistics.bowling_service.get_db_connection")
def test_player_not_found(mock_connection):
    mock_cursor = (
        mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    )
    mock_cursor.fetchone.return_value = None

    result = get_player_bowling_stats("unknown-player")

    assert result is None


def test_invalid_player_id():
    with pytest.raises(ValueError, match="non-empty string"):
        get_player_bowling_stats("")

    with pytest.raises(ValueError, match="non-empty string"):
        get_player_bowling_stats("   ")

    with pytest.raises(ValueError, match="non-empty string"):
        get_player_bowling_stats(None)


def test_invalid_leaderboard_limit():
    with pytest.raises(ValueError, match="between 1 and 100"):
        get_bowling_leaderboard(limit=0)

    with pytest.raises(ValueError, match="between 1 and 100"):
        get_bowling_leaderboard(limit=101)

    with pytest.raises(ValueError, match="integer"):
        get_bowling_leaderboard(limit="20")

    with pytest.raises(ValueError, match="integer"):
        get_bowling_leaderboard(limit=True)


@patch("app.services.statistics.bowling_service.get_db_connection")
def test_bowling_leaderboard(mock_connection):
    mock_cursor = (
        mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    )
    mock_cursor.fetchall.return_value = [BHUVI_ROW, MALINGA_ROW]

    results = get_bowling_leaderboard(limit=2)

    assert len(results) == 2
    assert results[0]["player_name"] == "B Kumar"
    assert results[0]["wickets"] == 226
    assert results[0]["maidens"] == 14
    assert results[1]["player_name"] == "SL Malinga"
    assert results[1]["wickets"] == 170


@patch("app.services.statistics.bowling_service.get_db_connection")
def test_best_bowling_figures_format(mock_connection):
    mock_cursor = (
        mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    )
    mock_cursor.fetchone.return_value = MALINGA_ROW

    result = get_player_bowling_stats("a12e1d51")

    assert result["best_bowling"] == "5/13"
    assert "/" in result["best_bowling"]
    wickets_str, runs_str = result["best_bowling"].split("/")
    assert int(wickets_str) == 5
    assert int(runs_str) == 13


@patch("app.services.statistics.bowling_service.get_db_connection")
def test_maiden_overs(mock_connection):
    mock_cursor = (
        mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    )
    mock_cursor.fetchone.return_value = BHUVI_ROW

    result = get_player_bowling_stats("2e81a32d")

    assert "maidens" in result
    assert isinstance(result["maidens"], int)
    assert result["maidens"] == 14


@patch("app.services.statistics.bowling_service.get_db_connection")
def test_zero_wickets_bowler(mock_connection):
    mock_cursor = (
        mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    )
    mock_cursor.fetchone.return_value = ZERO_WICKET_ROW

    result = get_player_bowling_stats("test_zero")

    assert result["wickets"] == 0
    assert result["bowling_average"] is None
    assert result["bowling_strike_rate"] is None
    assert result["best_bowling"] == "0/20"
    assert result["best_innings_wickets"] == 0
