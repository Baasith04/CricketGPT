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

