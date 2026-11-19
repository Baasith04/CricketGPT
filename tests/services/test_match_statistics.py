import pytest

from app.services.matches import (
    match_list_service,
    scorecard_service,
)


def test_match_list_invalid_limit():
    with pytest.raises(ValueError):
        match_list_service.get_matches(limit=101)


def test_match_list_negative_offset():
    with pytest.raises(ValueError):
        match_list_service.get_matches(offset=-1)


def test_match_list_invalid_date_range():
    with pytest.raises(ValueError):
        match_list_service.get_matches(
            start_date="2025-12-31",
            end_date="2025-01-01",
        )


def test_scorecard_invalid_match_id():
    with pytest.raises(ValueError):
        scorecard_service.get_match_scorecard(-1)


def test_scorecard_rejects_string_match_id():
    with pytest.raises(ValueError):
        scorecard_service.get_match_scorecard("335982")