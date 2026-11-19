"""
Inspect and safely dry-run backfill of NULL/stale historical match metadata
(`stage`, `match_number`, `cricsheet_revision`, `cricsheet_created_date`)
directly from `matches.raw_json` without touching deliveries or match outcomes.

Usage:
    python scripts/backfill_metadata.py           # Dry-run report only (default)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import get_db_connection


def inspect_historical_metadata_backfill() -> Dict[str, Any]:
    """
    Read-only dry-run audit showing how many existing `matches` rows have missing
    or stale metadata fields that can be deterministically backfilled from `raw_json`.
    """
    audit_sql = """
        SELECT
            COUNT(*)::INT AS total_matches,
            COUNT(*) FILTER (WHERE stage IS NULL)::INT AS null_stage,
            COUNT(*) FILTER (
                WHERE stage IS NULL
                  AND NULLIF(TRIM(raw_json->'info'->'event'->>'stage'), '') IS NOT NULL
            )::INT AS backfillable_stage,
            COUNT(*) FILTER (WHERE match_number IS NULL)::INT AS null_match_number,
            COUNT(*) FILTER (
                WHERE match_number IS NULL
                  AND (raw_json->'info'->'event'->>'match_number') ~ '^\\d+$'
            )::INT AS backfillable_match_number,
            COUNT(*) FILTER (
                WHERE NULLIF(raw_json->'meta'->>'revision', '') ~ '^\\d+$'
                  AND (raw_json->'meta'->>'revision')::INT <> cricsheet_revision
            )::INT AS backfillable_revision,
            COUNT(*) FILTER (WHERE cricsheet_created_date IS NULL)::INT AS null_created_date,
            COUNT(*) FILTER (
                WHERE cricsheet_created_date IS NULL
                  AND (raw_json->'meta'->>'created') ~ '^\\d{4}-\\d{2}-\\d{2}$'
            )::INT AS backfillable_created_date
        FROM matches;
    """
    sample_sql = """
        SELECT
            match_id,
            season,
            stage AS current_stage,
            NULLIF(TRIM(raw_json->'info'->'event'->>'stage'), '') AS raw_stage,
            match_number AS current_match_number,
            CASE
                WHEN (raw_json->'info'->'event'->>'match_number') ~ '^\\d+$'
                THEN (raw_json->'info'->'event'->>'match_number')::INT
                ELSE NULL
            END AS raw_match_number,
            cricsheet_revision AS current_revision,
            (raw_json->'meta'->>'revision')::INT AS raw_revision,
            cricsheet_created_date AS current_created_date,
            raw_json->'meta'->>'created' AS raw_created_date
        FROM matches
        WHERE stage IS NULL
           OR match_number IS NULL
           OR cricsheet_created_date IS NULL
        ORDER BY match_date DESC, match_id DESC
        LIMIT 5;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(audit_sql)
            cols = [c.name for c in cur.description]
            counts = dict(zip(cols, cur.fetchone()))
            cur.execute(sample_sql)
            s_cols = [c.name for c in cur.description]
            samples = [dict(zip(s_cols, r)) for r in cur.fetchall()]

    return {
        "dry_run": True,
        "schema_migration_required": False,
        "counts": counts,
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run audit of historical match metadata backfill from raw_json."
    )
    parser.parse_args()
    report = inspect_historical_metadata_backfill()
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

