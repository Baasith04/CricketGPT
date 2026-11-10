
import pytest

from app.ingestion.validators.scorecard_validator import (
    validate_innings,
    validate_all_innings,
)


def make_stored(**overrides):
    data = {
        "match_id": 335982,
        "innings_number": 1,
        "is_super_over": False,
        "total_runs": 222,
        "total_wickets": 3,
        "legal_balls_bowled": 120,
    }
    data.update(overrides)
    return data


def make_calculated(**overrides):
    data = {
        "total_runs": 222,
        "total_wickets": 3,
        "legal_balls_bowled": 120,
        "delivery_count": 120,
    }
    data.update(overrides)
    return data


def test_valid_innings():
    result = validate_innings(
        make_stored(),
        make_calculated(),
    )

    assert result["is_valid"] is True
    assert result["mismatches"] == []


@pytest.mark.parametrize(
    "field,stored,calculated",
    [
        ("total_runs", 222, 220),
        ("total_wickets", 3, 4),
        ("legal_balls_bowled", 120, 119),
    ],
)
def test_detects_each_mismatch(field, stored, calculated):
    stored_data = make_stored()
    calculated_data = make_calculated()

    stored_data[field] = stored
    calculated_data[field] = calculated

    result = validate_innings(
        stored_data,
        calculated_data,
    )

    assert result["is_valid"] is False
    assert result["mismatches"][0]["field"] == field


def test_super_over_metadata_is_preserved():
    result = validate_innings(
        make_stored(
            innings_number=3,
            is_super_over=True,
            total_runs=12,
            total_wickets=2,
            legal_balls_bowled=6,
        ),
        make_calculated(
            total_runs=12,
            total_wickets=2,
            legal_balls_bowled=6,
        ),
    )

    assert result["is_valid"] is True
    assert result["is_super_over"] is True


def test_validate_all_innings_summary():
    rows = [
        {
            **make_stored(),
            "total_runs_calculated": 222,
            "total_wickets_calculated": 3,
            "legal_balls_calculated": 120,
            "delivery_count": 120,
        },
        {
            **make_stored(
                match_id=335983,
                total_runs=150,
            ),
            "total_runs_calculated": 148,
            "total_wickets_calculated": 4,
            "legal_balls_calculated": 120,
            "delivery_count": 120,
        },
    ]

    report = validate_all_innings(rows)

    assert report["total_innings"] == 2
    assert report["valid_innings"] == 1
    assert report["invalid_innings"] == 1


def test_empty_innings_collection():
    report = validate_all_innings([])

    assert report["total_innings"] == 0
    assert report["valid_innings"] == 0
    assert report["invalid_innings"] == 0
