import pytest

from app.services.teams import team_service


def test_get_team_profile_found(monkeypatch):
    expected = {
        "team_id": 1,
        "team_name": "Chennai Super Kings",
        "short_code": "CSK",
        "matches_played": 10,
        "wins": 6,
        "losses": 3,
        "ties": 1,
        "no_results": 0,
    }

    monkeypatch.setattr(
        team_service,
        "_fetch_all",
        lambda query, params=(): [expected],
    )

    result = team_service.get_team_profile("CSK")

    assert result["team_name"] == "Chennai Super Kings"
    assert result["wins"] == 6


def test_get_team_profile_not_found(monkeypatch):
    monkeypatch.setattr(
        team_service,
        "_fetch_all",
        lambda query, params=(): [],
    )

    assert team_service.get_team_profile("Unknown Team") is None


def test_get_team_profile_ambiguous(monkeypatch):
    monkeypatch.setattr(
        team_service,
        "_fetch_all",
        lambda query, params=(): [
            {"team_name": "Team A"},
            {"team_name": "Team B"},
        ],
    )

    with pytest.raises(ValueError):
        team_service.get_team_profile("Team")