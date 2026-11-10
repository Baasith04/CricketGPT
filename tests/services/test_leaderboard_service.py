
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
