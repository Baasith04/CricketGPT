
import pytest

from app.services.statistics import leaderboard_service as service


def test_invalid_batting_category():
    with pytest.raises(ValueError):
        service.get_batting_leaderboard(category="invalid")


def test_invalid_bowling_category():
    with pytest.raises(ValueError):
        service.get_bowling_leaderboard(category="invalid")


def test_invalid_limit():
    with pytest.raises(ValueError):
        service.get_batting_leaderboard(limit=101)


def test_zero_limit():
    with pytest.raises(ValueError):
        service.get_bowling_leaderboard(limit=0)


def test_negative_min_balls():
    with pytest.raises(ValueError):
        service.get_batting_leaderboard(min_balls=-1)


def test_invalid_season_type():
    with pytest.raises(ValueError):
        service.get_bowling_leaderboard(season=2025)


def test_empty_season():
    with pytest.raises(ValueError):
        service.get_batting_leaderboard(season=" ")


def test_invalid_min_balls_type():
    with pytest.raises(ValueError):
        service.get_bowling_leaderboard(min_balls=2.5)


def test_dot_balls_bowling_leaderboard_sql_and_params(monkeypatch):
    captured = {}

    def fake_fetch_all(query, params):
        captured["query"] = query
        captured["params"] = params
        return [
            {"player_name": "B Kumar", "dot_balls": 1897, "matches_played": 176},
            {"player_name": "SP Narine", "dot_balls": 1784, "matches_played": 177},
        ]

    monkeypatch.setattr(service, "_fetch_all", fake_fetch_all)

    rows = service.get_bowling_leaderboard(category="dot_balls", season="2024", limit=5)

    assert len(rows) == 2
    assert rows[0]["player_name"] == "B Kumar"
    assert rows[0]["dot_balls"] == 1897
    assert "d.is_legal_ball = TRUE" in captured["query"]
    assert "COALESCE(d.total_runs, 0) = 0" in captured["query"]
    assert "i.is_super_over = FALSE" in captured["query"]
    assert "ORDER BY dot_balls DESC, legal_balls ASC, player_name ASC" in captured["query"]
    assert captured["params"] == ("2024", "2024", 0, 5)


def test_single_match_dot_balls_sql_and_validation(monkeypatch):
    with pytest.raises(ValueError):
        service.get_most_dot_balls_in_match(limit=0)
    with pytest.raises(ValueError):
        service.get_most_dot_balls_in_match(season="  ")

    captured = {}

    def fake_fetch_all(query, params):
        captured["query"] = query
        captured["params"] = params
        return []

    monkeypatch.setattr(service, "_fetch_all", fake_fetch_all)
    rows = service.get_most_dot_balls_in_match(season=" 2024 ", limit=5)
    assert rows == []
    assert "d.is_legal_ball = TRUE" in captured["query"]
    assert "COALESCE(d.total_runs, 0) = 0" in captured["query"]
    assert "ORDER BY" in captured["query"]
    assert "dot_balls DESC" in captured["query"]
    assert captured["params"] == ("2024", "2024", 5)
