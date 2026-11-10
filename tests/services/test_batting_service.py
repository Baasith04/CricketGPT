
from unittest.mock import patch

import pytest

from app.services.statistics.batting_service import (
    get_batting_leaderboard,
    get_player_batting_stats,
)


KOHLI_ROW = (
    "ba607b88",
    "V Kohli",
    275,
    275,
    9336,
    46,
    40.77,
    6926,
    134.80,
    845,
    317,
    68,
    9,
    113,
)


@patch("app.services.statistics.batting_service.get_db_connection")
def test_get_player_batting_stats(mock_connection):
    mock_cursor = mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cursor.fetchone.return_value = KOHLI_ROW

    result = get_player_batting_stats("ba607b88")

    assert result["player_name"] == "V Kohli"
    assert result["total_runs"] == 9336
    assert result["batting_average"] == 40.77
    assert result["strike_rate"] == 134.80


@patch("app.services.statistics.batting_service.get_db_connection")
def test_player_not_found(mock_connection):
    mock_cursor = mock_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    mock_cursor.fetchone.return_value = None

    result = get_player_batting_stats("unknown-player")

    assert result is None


def test_invalid_player_id():
    with pytest.raises(ValueError):
        get_player_batting_stats("")


def test_invalid_leaderboard_limit():
    with pytest.raises(ValueError):
        get_batting_leaderboard(limit=0)
