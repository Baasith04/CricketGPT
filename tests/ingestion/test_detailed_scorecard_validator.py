
from app.ingestion.validators.detailed_scorecard_validator import (
    calculate_detailed_scorecards,
)


def sample_data():
    deliveries = [
        {
            "delivery_id": 1,
            "innings_id": 10,
            "match_id": 100,
            "batter_id": "P1",
            "batter_name": "Player One",
            "bowler_id": "P2",
            "bowler_name": "Player Two",
            "batter_runs": 4,
            "extra_runs": 0,
            "total_runs": 4,
            "wide_runs": 0,
            "no_ball_runs": 0,
            "bye_runs": 0,
            "leg_bye_runs": 0,
            "penalty_runs": 0,
            "is_legal_ball": True,
        },
        {
            "delivery_id": 2,
            "innings_id": 10,
            "match_id": 100,
            "batter_id": "P1",
            "batter_name": "Player One",
            "bowler_id": "P2",
            "bowler_name": "Player Two",
            "batter_runs": 1,
            "extra_runs": 1,
            "total_runs": 2,
            "wide_runs": 1,
            "no_ball_runs": 0,
            "bye_runs": 0,
            "leg_bye_runs": 0,
            "penalty_runs": 0,
            "is_legal_ball": False,
        },
        {
            "delivery_id": 3,
            "innings_id": 10,
            "match_id": 100,
            "batter_id": "P1",
            "batter_name": "Player One",
            "bowler_id": "P2",
            "bowler_name": "Player Two",
            "batter_runs": 2,
            "extra_runs": 0,
            "total_runs": 2,
            "wide_runs": 0,
            "no_ball_runs": 0,
            "bye_runs": 0,
            "leg_bye_runs": 0,
            "penalty_runs": 0,
            "is_legal_ball": True,
        },
    ]

    wickets = [
        {
            "wicket_id": 1,
            "delivery_id": 3,
            "innings_id": 10,
            "match_id": 100,
            "dismissal_kind": "bowled",
            "player_dismissed_id": "P1",
            "player_dismissed_name": "Player One",
            "is_bowler_credit": True,
        }
    ]

    innings = [
        {
            "innings_id": 10,
            "match_id": 100,
            "innings_number": 1,
            "is_super_over": False,
            "total_runs": 8,
            "total_wickets": 1,
            "legal_balls_bowled": 2,
        }
    ]

    return deliveries, wickets, innings


def test_batter_runs_and_balls_faced():
    deliveries, wickets, innings = sample_data()

    result = calculate_detailed_scorecards(
        deliveries, wickets, innings
    )

    batter = result["batters"][0]

    assert batter["runs"] == 7
    assert batter["balls_faced"] == 2
    assert batter["fours"] == 1
    assert batter["strike_rate"] == 350.0


def test_wide_is_not_counted_as_batter_ball():
    deliveries, wickets, innings = sample_data()

    result = calculate_detailed_scorecards(
        deliveries, wickets, innings
    )

    assert result["batters"][0]["balls_faced"] == 2


def test_bowler_figures():
    deliveries, wickets, innings = sample_data()

    result = calculate_detailed_scorecards(
        deliveries, wickets, innings
    )

    bowler = result["bowlers"][0]

    assert bowler["runs_conceded"] == 8
    assert bowler["legal_balls"] == 2
    assert bowler["wickets"] == 1
    assert bowler["overs"] == "0.2"
    assert bowler["economy"] == 24.0


def test_innings_reconciliation_passes():
    deliveries, wickets, innings = sample_data()

    result = calculate_detailed_scorecards(
        deliveries, wickets, innings
    )

    assert result["valid_innings"] == 1
    assert result["invalid_innings"] == 0


def test_innings_runs_mismatch_is_detected():
    deliveries, wickets, innings = sample_data()
    innings[0]["total_runs"] = 9

    result = calculate_detailed_scorecards(
        deliveries, wickets, innings
    )

    assert result["invalid_innings"] == 1
    assert result["innings"][0]["is_valid"] is False


def test_retired_hurt_is_not_counted_as_dismissal():
    deliveries, wickets, innings = sample_data()

    wickets[0]["dismissal_kind"] = "retired hurt"

    result = calculate_detailed_scorecards(
        deliveries, wickets, innings
    )

    assert result["batters"][0]["dismissals"] == 0
    assert result["bowlers"][0]["wickets"] == 0
    assert result["innings"][0]["calculated_wickets"] == 0
