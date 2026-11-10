"""Tests for Cricsheet metadata parsing and post-import scorecard validation."""

import json
from unittest.mock import MagicMock, patch

from app.ingestion.parser import parse_match
from app.ingestion.validators.scorecard_validator import validate_imported_match


def test_parse_match_extracts_stage_match_number_and_meta(tmp_path):
    raw_final = {
        "meta": {"revision": 2, "created": "2026-06-01"},
        "info": {
            "season": "2026",
            "dates": ["2026-05-31"],
            "venue": "M Chinnaswamy Stadium",
            "city": "Bengaluru",
            "teams": ["Royal Challengers Bengaluru", "Sunrisers Hyderabad"],
            "event": {"name": "Indian Premier League", "stage": "Final"},
            "players": {
                "Royal Challengers Bengaluru": ["V Kohli"],
                "Sunrisers Hyderabad": ["Abhishek Sharma"],
            },
            "registry": {"people": {"V Kohli": "ba607b88", "Abhishek Sharma": "c1234567"}},
            "outcome": {"winner": "Royal Challengers Bengaluru", "by": {"wickets": 6}},
        },
        "innings": [],
    }
    fpath = tmp_path / "1535465.json"
    fpath.write_text(json.dumps(raw_final), encoding="utf-8")

    parsed = parse_match(fpath)
    assert parsed["stage"] == "Final"
    assert parsed["match_number"] is None
    assert parsed["cricsheet_revision"] == 2
    assert parsed["cricsheet_created_date"] == "2026-06-01"

    raw_league = {
        "meta": {"revision": 1, "created": "2026-05-25"},
        "info": {
            **raw_final["info"],
            "event": {"name": "Indian Premier League", "match_number": 70},
        },
        "innings": [],
    }
    lpath = tmp_path / "1529313.json"
    lpath.write_text(json.dumps(raw_league), encoding="utf-8")
    parsed_league = parse_match(lpath)
    assert parsed_league["stage"] is None
    assert parsed_league["match_number"] == 70


@patch("app.ingestion.validators.scorecard_validator.get_db_connection")
def test_validate_imported_match_checks_stored_vs_delivery_totals(mock_conn):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    col_names = [
        "match_id", "innings_number", "is_super_over",
        "total_runs", "total_wickets", "legal_balls_bowled",
        "total_runs_calculated", "total_wickets_calculated",
        "legal_balls_calculated", "delivery_count",
    ]
    cur.description = [MagicMock(name=n) for n in col_names]
    for c, n in zip(cur.description, col_names):
        c.name = n
    cur.fetchall.return_value = [
        (1535465, 1, False, 190, 7, 120, 190, 7, 120, 124),
        (1535465, 2, False, 191, 4, 116, 191, 4, 116, 119),
    ]

    res = validate_imported_match(1535465)
    assert res["match_id"] == 1535465
    assert res["is_valid"] is True
    assert res["total_innings"] == 2
    assert res["invalid_innings"] == 0


@patch("scripts.backfill_metadata.get_db_connection")
def test_inspect_historical_metadata_backfill_dry_run(mock_conn):
    from scripts.backfill_metadata import inspect_historical_metadata_backfill

    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    count_cols = [
        "total_matches", "null_stage", "backfillable_stage",
        "null_match_number", "backfillable_match_number",
        "backfillable_revision", "null_created_date", "backfillable_created_date",
    ]
    sample_cols = [
        "match_id", "season", "current_stage", "raw_stage",
        "current_match_number", "raw_match_number",
        "current_revision", "raw_revision",
        "current_created_date", "raw_created_date",
    ]
    cur.description = [MagicMock() for _ in count_cols]
    for c, n in zip(cur.description, count_cols):
        c.name = n
    cur.fetchone.return_value = (1243, 1243, 74, 1243, 1169, 1243, 1243, 1243)

    # Second query uses sample_cols
    def _fetchall():
        cur.description = [MagicMock() for _ in sample_cols]
        for c, n in zip(cur.description, sample_cols):
            c.name = n
        return [(1535465, "2026", None, "Final", None, None, 1, 2, None, "2026-06-01")]

    cur.fetchall.side_effect = _fetchall

    report = inspect_historical_metadata_backfill()
    assert report["dry_run"] is True
    assert report["schema_migration_required"] is False
    assert report["counts"]["backfillable_stage"] == 74
    assert report["counts"]["backfillable_match_number"] == 1169

