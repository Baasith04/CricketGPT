
import json

from psycopg.rows import dict_row

from app.database.connection import get_db_connection
from app.ingestion.validators.scorecard_validator import (
    validate_all_innings,
)


VALIDATION_QUERY = """

WITH delivery_totals AS (
    SELECT
        d.match_id,
        d.innings_id,
        SUM(d.total_runs) AS total_runs_calculated,
        COUNT(*) AS delivery_count,
        COUNT(*) FILTER (
            WHERE d.is_legal_ball = TRUE
        ) AS legal_balls_calculated
    FROM deliveries d
    GROUP BY d.match_id, d.innings_id
),

wicket_totals AS (
    SELECT
        d.match_id,
        d.innings_id,
        COUNT(w.wicket_id) FILTER (
            WHERE LOWER(w.dismissal_kind) <> 'retired hurt'
        ) AS total_wickets_calculated
    FROM deliveries d
    LEFT JOIN delivery_wickets w
        ON w.delivery_id = d.delivery_id
    GROUP BY d.match_id, d.innings_id
)

SELECT
    i.match_id,
    i.innings_number,
    i.is_super_over,
    i.total_runs,
    i.total_wickets,
    i.legal_balls_bowled,

    COALESCE(dt.total_runs_calculated, 0)
        AS total_runs_calculated,

    COALESCE(wt.total_wickets_calculated, 0)
        AS total_wickets_calculated,

    COALESCE(dt.legal_balls_calculated, 0)
        AS legal_balls_calculated,

    COALESCE(dt.delivery_count, 0)
        AS delivery_count

FROM innings i

LEFT JOIN delivery_totals dt
    ON dt.match_id = i.match_id
    AND dt.innings_id = i.innings_id

LEFT JOIN wicket_totals wt
    ON wt.match_id = i.match_id
    AND wt.innings_id = i.innings_id

ORDER BY i.match_id, i.innings_number;  
"""


def main():
    print("Connecting to Supabase...")

    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(VALIDATION_QUERY)
            rows = cur.fetchall()

    report = validate_all_innings(rows)

    print("\n========== SCORECARD AUDIT ==========")
    print(f"Total innings: {report['total_innings']}")
    print(f"Valid innings: {report['valid_innings']}")
    print(f"Invalid innings: {report['invalid_innings']}")

    failures = [
        result for result in report["results"]
        if not result["is_valid"]
    ]

    if failures:
        print("\n========== MISMATCH DETAILS ==========")

        for result in failures:
            print(json.dumps(result, indent=4, default=str))

    output_path = "scorecard_validation_report.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, default=str)

    print(f"\nReport saved: {output_path}")

    if failures:
        raise SystemExit(
            f"Audit found {len(failures)} invalid innings."
        )

    print("\nAll innings passed the three reconciliation checks.")


if __name__ == "__main__":
    main()
