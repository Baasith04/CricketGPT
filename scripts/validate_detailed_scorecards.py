
import json
from pathlib import Path

from psycopg.rows import dict_row

from app.database.connection import get_db_connection
from app.ingestion.validators.detailed_scorecard_validator import (
    calculate_detailed_scorecards,
)


DELIVERIES_QUERY = """
SELECT
    delivery_id,
    innings_id,
    match_id,
    batter_id,
    batter_name,
    bowler_id,
    bowler_name,
    batter_runs,
    extra_runs,
    total_runs,
    wide_runs,
    no_ball_runs,
    bye_runs,
    leg_bye_runs,
    penalty_runs,
    is_legal_ball
FROM deliveries
ORDER BY match_id, innings_id, over_number, delivery_sequence;
"""

WICKETS_QUERY = """
SELECT
    w.wicket_id,
    w.delivery_id,
    d.innings_id,
    w.match_id,
    w.dismissal_kind,
    w.player_dismissed_id,
    w.player_dismissed_name,
    w.is_bowler_credit
FROM delivery_wickets w
JOIN deliveries d
    ON d.delivery_id = w.delivery_id
ORDER BY w.match_id, w.wicket_id;
"""

INNINGS_QUERY = """
SELECT
    innings_id,
    match_id,
    innings_number,
    is_super_over,
    total_runs,
    total_wickets,
    legal_balls_bowled
FROM innings
ORDER BY match_id, innings_number;
"""



def main():
    print("Connecting to Supabase...")

    with get_db_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cur:
            print("Fetching deliveries...")
            cur.execute(DELIVERIES_QUERY)
            deliveries = cur.fetchall()

            print("Fetching wickets...")
            cur.execute(WICKETS_QUERY)
            wickets = cur.fetchall()

            print("Fetching innings...")
            cur.execute(INNINGS_QUERY)
            innings = cur.fetchall()

    print("Calculating detailed scorecards...")

    report = calculate_detailed_scorecards(
        delivery_rows=deliveries,
        wicket_rows=wickets,
        innings_rows=innings,
    )

    output_path = Path("detailed_scorecard_validation_report.json")

    output_path.write_text(
        json.dumps(report, indent=4, default=str),
        encoding="utf-8",
    )

    print("\n========== DETAILED SCORECARD AUDIT ==========")
    print(f"Deliveries: {len(deliveries)}")
    print(f"Wickets: {len(wickets)}")
    print(f"Total innings: {report['total_innings']}")
    print(f"Valid innings: {report['valid_innings']}")
    print(f"Invalid innings: {report['invalid_innings']}")
    print(f"Batters calculated: {report['batters_calculated']}")
    print(f"Bowlers calculated: {report['bowlers_calculated']}")

    if report["invalid_innings"]:
        print("\nMISMATCHES:")
        for result in report["innings"]:
            if not result["is_valid"]:
                print(json.dumps(result, indent=2))

    print(f"\nReport saved: {output_path}")

    if report["invalid_innings"]:
        raise SystemExit(
            "Detailed scorecard audit found mismatches."
        )

    print("\nAll innings passed detailed reconciliation checks.")



if __name__ == "__main__":
    main()
