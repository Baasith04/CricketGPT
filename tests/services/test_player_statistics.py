import pytest

from app.services.players import player_comparison_service as comparison


def test_compare_two_players(monkeypatch):
    def fake_batting(name):
        return [{
            "player_id": name,
            "player_name": name,
            "total_runs": 100,
        }]

    def fake_bowling(name):
        return [{
            "player_id": name,
            "player_name": name,
            "wickets": 5,
        }]

    monkeypatch.setattr(
        comparison,
        "get_player_batting_stats",
        fake_batting,
    )
    monkeypatch.setattr(
        comparison,
        "get_player_bowling_stats",
        fake_bowling,
    )

    result = comparison.compare_players("Player A", "Player B")

    assert result["player_one"]["batting"]["total_runs"] == 100
    assert result["player_one"]["bowling"]["wickets"] == 5
    assert result["player_two"]["batting"]["total_runs"] == 100
    assert result["player_two"]["bowling"]["wickets"] == 5


def test_compare_same_player():
    with pytest.raises(ValueError):
        comparison.compare_players("Virat Kohli", "virat kohli")


def test_compare_missing_player(monkeypatch):
    monkeypatch.setattr(
        comparison,
        "get_player_batting_stats",
        lambda name: [],
    )
    monkeypatch.setattr(
        comparison,
        "get_player_bowling_stats",
        lambda name: [],
    )

    with pytest.raises(ValueError):
        comparison.compare_players("Unknown Player", "Player B")


def test_compare_ambiguous_player(monkeypatch):
    monkeypatch.setattr(
        comparison,
        "get_player_batting_stats",
        lambda name: [
            {"player_name": "Player A"},
            {"player_name": "Player A Another"},
        ],
    )
    monkeypatch.setattr(
        comparison,
        "get_player_bowling_stats",
        lambda name: [
            {"player_name": "Player A"},
            {"player_name": "Player A Another"},
        ],
    )

    with pytest.raises(ValueError):
        comparison.compare_players("Player A", "Player B")