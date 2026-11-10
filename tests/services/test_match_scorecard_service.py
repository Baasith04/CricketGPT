from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pytest

from app.services.matches import match_service, scorecard_service


MOCK_MATCH_ROW = (
    335982,
    "2007/08",
    date(2008, 4, 18),
    "M Chinnaswamy Stadium, Bangalore",
    "Bangalore",
    None,
    14,
    "Royal Challengers Bengaluru",
    "field",
    8,
    "Kolkata Knight Riders",
    "runs",
    None,
    140,
    None,
    False,
    {"by": {"runs": 140}, "winner": "Kolkata Knight Riders"},
)

MOCK_TEAM_ROWS = [
    (1, 14, "Royal Challengers Bengaluru", "RCB", "Royal Challengers Bangalore"),
    (2, 8, "Kolkata Knight Riders", "KKR", "Kolkata Knight Riders"),
]


# ---------------------------------------------------------------------------
# Match Details Tests
# ---------------------------------------------------------------------------

@patch("app.services.matches.match_service.get_db_connection")
def test_get_match_details_success(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = MOCK_MATCH_ROW
    cur.fetchall.return_value = MOCK_TEAM_ROWS

    result = match_service.get_match_details(335982)

    assert result is not None
    assert result["match_id"] == 335982
    assert result["season"] == "2007/08"
    assert result["match_date"] == "2008-04-18"
    assert len(result["teams"]) == 2
    assert result["toss"]["toss_winner_name"] == "Royal Challengers Bengaluru"
    assert result["result"]["winner_name"] == "Kolkata Knight Riders"
    assert result["result"]["summary"] == "Kolkata Knight Riders won by 140 runs"


@patch("app.services.matches.match_service.get_db_connection")
def test_get_match_details_super_over_eliminator(mock_conn):
    so_row = (
        598004,
        "2013",
        date(2013, 4, 7),
        "Rajiv Gandhi International Stadium",
        "Hyderabad",
        None,
        14,
        "Royal Challengers Bengaluru",
        "bat",
        None,
        None,
        "no result",
        None,
        None,
        None,
        True,
        {"result": "tie", "eliminator": "Sunrisers Hyderabad"},
    )
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = so_row
    cur.fetchall.return_value = MOCK_TEAM_ROWS

    result = match_service.get_match_details(598004)

    assert result["result"]["is_super_over"] is True
    assert result["result"]["winner_name"] == "Sunrisers Hyderabad"
    assert "Super Over" in result["result"]["summary"]


@patch("app.services.matches.match_service.get_db_connection")
def test_get_match_details_not_found(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = None

    assert match_service.get_match_details(999999) is None


def test_get_match_details_invalid_id():
    with pytest.raises(ValueError):
        match_service.get_match_details(0)
    with pytest.raises(ValueError):
        match_service.get_match_details(-5)
    with pytest.raises(ValueError):
        match_service.get_match_details("335982")
    with pytest.raises(ValueError):
        match_service.get_match_details(True)


# ---------------------------------------------------------------------------
# Dismissal Text Formatting Tests
# ---------------------------------------------------------------------------

def test_format_dismissal_text():
    assert scorecard_service._format_dismissal_text(False, None, None, None) == "not out"
    assert scorecard_service._format_dismissal_text(False, "retired hurt", None, None) == "retired hurt"
    assert scorecard_service._format_dismissal_text(True, "bowled", "I Sharma", []) == "b I Sharma"
    assert scorecard_service._format_dismissal_text(True, "caught", "Z Khan", ["JH Kallis"]) == "c JH Kallis b Z Khan"
    assert scorecard_service._format_dismissal_text(True, "caught and bowled", "DJ Bravo", []) == "c & b DJ Bravo"
    assert scorecard_service._format_dismissal_text(True, "lbw", "Rashid Khan", []) == "lbw b Rashid Khan"
    assert scorecard_service._format_dismissal_text(True, "stumped", "YS Chahal", ["MS Dhoni"]) == "st MS Dhoni b YS Chahal"
    assert scorecard_service._format_dismissal_text(True, "run out", "SC Ganguly", ["AB Agarkar", "WP Saha"]) == "run out (AB Agarkar/WP Saha)"


# ---------------------------------------------------------------------------
# Scorecard Service Tests
# ---------------------------------------------------------------------------

@patch("app.services.matches.scorecard_service.get_match_details")
@patch("app.services.matches.scorecard_service.get_db_connection")
def test_get_match_scorecard_with_super_over(mock_conn, mock_details):
    mock_details.return_value = {
        "match_id": 598004,
        "result": {"is_super_over": True},
    }

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    # 1 regular innings + 1 super over innings
    innings_rows = [
        (1, 1, 14, "Royal Challengers Bengaluru", 15, "Sunrisers Hyderabad", 130, 8, 120, False, None),
        (3, 3, 15, "Sunrisers Hyderabad", 14, "Royal Challengers Bengaluru", 20, 0, 6, True, None),
    ]
    # Fetchall sequence: innings_rows, inn1 batting, inn1 bowling, inn3 batting, inn3 bowling
    cur.fetchall.side_effect = [
        innings_rows,
        [("p1", "V Kohli", 46, 30, 5, 1, Decimal("153.33"), True, "caught", "DW Steyn", ["PA Patel"]),
         ("p2", "CH Gayle", 15, 12, 1, 1, Decimal("125.00"), False, "retired hurt", None, [])],
        [("b1", "DW Steyn", 24, 1, 20, 2, Decimal("5.00"), 1, 0)],
        [("p3", "CL White", 12, 4, 0, 2, Decimal("300.00"), False, None, None, [])],
        [("b2", "R Vinay Kumar", 6, 0, 20, 0, Decimal("20.00"), 0, 0)],
    ]
    # Fetchone sequence: inn1 extras, inn3 extras
    cur.fetchone.side_effect = [
        (2, 0, 0, 3, 0, 5),
        (0, 0, 0, 0, 0, 0),
    ]

    result = scorecard_service.get_match_scorecard(598004)

    assert result is not None
    assert result["has_super_over"] is True
    assert len(result["innings"]) == 1
    assert len(result["super_overs"]) == 1

    inn1 = result["innings"][0]
    assert inn1["overs"] == "20.0"
    assert inn1["batting"][0]["dismissal"] == "c PA Patel b DW Steyn"
    assert inn1["batting"][1]["is_out"] is False
    assert inn1["batting"][1]["dismissal"] == "retired hurt"
    assert inn1["bowling"][0]["maidens"] == 1
    assert inn1["extras"]["total_extras"] == 5

    so1 = result["super_overs"][0]
    assert so1["is_super_over"] is True
    assert so1["overs"] == "1.0"
    assert so1["batting"][0]["dismissal"] == "not out"


@patch("app.services.matches.scorecard_service.get_match_details")
def test_get_match_scorecard_not_found(mock_details):
    mock_details.return_value = None
    assert scorecard_service.get_match_scorecard(999999) is None


# ---------------------------------------------------------------------------
# Wickets Service Tests
# ---------------------------------------------------------------------------

@patch("app.services.matches.scorecard_service.get_db_connection")
def test_get_match_wickets_success(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = (1,)
    cur.fetchall.side_effect = [
        # innings rows (1 regular + 1 super over with 0 wickets)
        [
            (1, 1, 8, "Kolkata Knight Riders", False, 222, 3),
            (3, 3, 8, "Kolkata Knight Riders", True, 15, 0),
        ],
        # wicket rows
        [
            (1, 1, "725529bc", "SC Ganguly", "caught", "91a4a398", "Z Khan", ["JH Kallis"], 61, 32, 5, 2),
        ],
    ]

    result = scorecard_service.get_match_wickets(335982)

    assert result is not None
    assert result["match_id"] == 335982
    assert result["has_super_over"] is True
    assert len(result["innings"]) == 1
    assert len(result["super_overs"]) == 1
    assert len(result["innings"][0]["fall_of_wickets"]) == 1
    assert result["innings"][0]["fall_of_wickets"][0]["overs"] == "5.2"
    assert result["innings"][0]["fall_of_wickets"][0]["score"] == 61
    assert result["super_overs"][0]["fall_of_wickets"] == []


@patch("app.services.matches.scorecard_service.get_db_connection")
def test_get_match_wickets_not_found(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = None

    assert scorecard_service.get_match_wickets(999999) is None


def test_get_match_wickets_invalid_id():
    with pytest.raises(ValueError):
        scorecard_service.get_match_wickets(-1)
    with pytest.raises(ValueError):
        scorecard_service.get_match_wickets("335982")


# ---------------------------------------------------------------------------
# Playoff Stage Resolution Tests
# ---------------------------------------------------------------------------

def test_normalize_playoff_stage_distinguishes_all_four_stages():
    assert match_service.normalize_playoff_stage("Qualifier 1") == "qualifier_1"
    assert match_service.normalize_playoff_stage("1st Qualifier") == "qualifier_1"
    assert match_service.normalize_playoff_stage("Second Qualifier") == "qualifier_2"
    assert match_service.normalize_playoff_stage("Qualifier-2") == "qualifier_2"
    assert match_service.normalize_playoff_stage("Eliminator") == "eliminator"
    assert match_service.normalize_playoff_stage("Elimination Final") == "eliminator"
    assert match_service.normalize_playoff_stage("Final") == "final"
    assert match_service.normalize_playoff_stage("Qualifier") is None
    assert match_service.normalize_playoff_stage("Semi Final") is None


@patch("app.services.matches.match_service.get_db_connection")
def test_resolve_playoff_match_qualifier_2_resolved(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [
        (1426311, "2024", date(2024, 5, 24), "Qualifier 2", "Sunrisers Hyderabad", "runs", None, 36, None),
    ]

    result = match_service.resolve_playoff_match("2024", "second qualifier")

    assert result["status"] == "resolved"
    assert result["stage"] == "qualifier_2"
    assert result["match"]["match_id"] == 1426311
    assert result["match"]["stage"] == "Qualifier 2"
    executed_params = cur.execute.call_args.args[1]
    assert executed_params == ("2024", ["Qualifier 2"])


@patch("app.services.matches.match_service.get_db_connection")
def test_resolve_playoff_match_eliminator_supports_elimination_final(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [
        (981015, "2016", date(2016, 5, 25), "Elimination Final", "Sunrisers Hyderabad", "runs", None, 22, None),
    ]

    result = match_service.resolve_playoff_match("2016", "eliminator")

    assert result["status"] == "resolved"
    assert result["match"]["match_id"] == 981015
    assert result["match"]["stage"] == "Elimination Final"
    executed_params = cur.execute.call_args.args[1]
    assert executed_params == ("2016", ["Eliminator", "Elimination Final"])


@patch("app.services.matches.match_service.get_db_connection")
def test_resolve_playoff_match_missing_returns_not_found_without_guessing(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = []

    result = match_service.resolve_playoff_match("2007/08", "qualifier_2")

    assert result["status"] == "not_found"
    assert result["match"] is None
    assert result["matches"] == []


@patch("app.services.matches.match_service.get_db_connection")
def test_resolve_playoff_match_multiple_rows_returns_ambiguous(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [
        (1001, "2024", date(2024, 5, 23), "Qualifier 2", "Team A", "runs", None, 10, None),
        (1002, "2024", date(2024, 5, 24), "Qualifier 2", "Team B", "wickets", None, None, 5),
    ]

    result = match_service.resolve_playoff_match("2024", "qualifier_2")

    assert result["status"] == "ambiguous"
    assert result["match"] is None
    assert len(result["matches"]) == 2


def test_resolve_playoff_match_invalid_inputs_raise():
    with pytest.raises(ValueError):
        match_service.resolve_playoff_match("", "qualifier_2")
    with pytest.raises(ValueError):
        match_service.resolve_playoff_match("2024", "semi_final")

