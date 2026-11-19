"""Unit tests for advanced statistics service and player name resolution."""

from unittest.mock import patch

import pytest

from app.services.players.player_service import resolve_player_sql_filter
from app.services.statistics import advanced_stats_service as adv


def test_resolve_player_sql_filter_known_alias():
    predicate, params = resolve_player_sql_filter("Virat Kohli")
    assert predicate == "p.canonical_name ILIKE %s"
    assert params == ("V Kohli",)


def test_resolve_player_sql_filter_dynamic_initial_surname():
    predicate, params = resolve_player_sql_filter("Trent Boult")
    assert "~*" in predicate
    assert params[0] == "%Trent Boult%"
    assert params[1].startswith("^T[A-Za-z]")
    assert "Boult" in params[1]


def test_get_biggest_victories_invalid_by_raises():
    with pytest.raises(ValueError, match="must be 'runs' or 'wickets'"):
        adv.get_biggest_victories(by="balls")


def test_get_phase_statistics_invalid_phase_raises():
    with pytest.raises(ValueError, match="Phase must be"):
        adv.get_phase_statistics(phase="superover")


def test_get_match_last_over_invalid_id_raises():
    with pytest.raises(ValueError, match="positive integer"):
        adv.get_match_last_over(-1)


@patch("app.services.statistics.advanced_stats_service._fetch_all")
def test_get_player_season_breakdown_not_found(mock_fetch):
    mock_fetch.return_value = []
    res = adv.get_player_season_breakdown("Nonexistent Player")
    assert res["seasons"] == []


@patch("app.services.statistics.advanced_stats_service._fetch_all")
def test_get_match_last_over_none_when_no_innings(mock_fetch):
    mock_fetch.return_value = []
    assert adv.get_match_last_over(999999) is None


@patch("app.services.statistics.advanced_stats_service._fetch_all")
def test_get_extras_and_dismissals_summary_structure(mock_fetch):
    mock_fetch.side_effect = [
        [{
            "total_deliveries": 1000,
            "total_extras": 50,
            "wide_runs": 30,
            "no_ball_runs": 5,
            "leg_bye_runs": 10,
            "bye_runs": 5,
            "penalty_runs": 0,
        }],
        [
            {"dismissal_kind": "caught", "total_count": 40, "is_bowler_credit": True},
        ],
    ]
    res = adv.get_extras_and_dismissals_summary(season="2024")
    assert res["season"] == "2024"
    assert res["extras"]["wide_runs"] == 30
    assert res["dismissals"][0]["dismissal_kind"] == "caught"

