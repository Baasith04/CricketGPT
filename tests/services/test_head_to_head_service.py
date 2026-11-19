import pytest

from app.services.teams import head_to_head_service as service


def test_head_to_head_same_team(monkeypatch):
    monkeypatch.setattr(
        service,
        "_find_team",
        lambda name: {
            "team_id": 1,
            "team_name": "Chennai Super Kings",
        },
    )

    with pytest.raises(ValueError):
        service.get_head_to_head("CSK", "Chennai Super Kings")


def test_head_to_head_missing_team(monkeypatch):
    def fake_find_team(name):
        if name == "Unknown":
            raise ValueError("Team not found.")

        return {"team_id": 1, "team_name": "Chennai Super Kings"}

    monkeypatch.setattr(service, "_find_team", fake_find_team)

    with pytest.raises(ValueError):
        service.get_head_to_head("CSK", "Unknown")


def test_head_to_head_requires_both_teams():
    with pytest.raises(ValueError):
        service.get_head_to_head("", "MI")