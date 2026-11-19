
from app.database.connection import get_db_connection


def validate_innings(stored, calculated):
    fields = (
        "total_runs",
        "total_wickets",
        "legal_balls_bowled",
    )

    mismatches = []

    for field in fields:
        expected = stored[field]
        actual = calculated[field]

        if expected != actual:
            mismatches.append({
                "field": field,
                "stored": expected,
                "calculated": actual,
            })

    return {
        "match_id": stored["match_id"],
        "innings_number": stored["innings_number"],
        "is_super_over": stored["is_super_over"],
        "delivery_count": calculated["delivery_count"],
        "is_valid": not mismatches,
        "mismatches": mismatches,
    }


def validate_all_innings(rows):
    results = []

    for row in rows:
        stored = {
            "match_id": row["match_id"],
            "innings_number": row["innings_number"],
            "is_super_over": row["is_super_over"],
            "total_runs": row["total_runs"],
            "total_wickets": row["total_wickets"],
            "legal_balls_bowled": row["legal_balls_bowled"],
        }

        calculated = {
            "total_runs": row["total_runs_calculated"],
            "total_wickets": row["total_wickets_calculated"],
            "legal_balls_bowled": row["legal_balls_calculated"],
            "delivery_count": row["delivery_count"],
        }

        results.append(validate_innings(stored, calculated))

    return {
        "total_innings": len(results),
        "valid_innings": sum(r["is_valid"] for r in results),
        "invalid_innings": sum(not r["is_valid"] for r in results),
        "results": results,
    }


def validate_imported_match(match_id: int):
    """
    Validate stored innings totals for one imported match against raw deliveries
    and delivery_wickets rows in Supabase (reusing `validate_all_innings`).
    """
    query = """
        WITH delivery_agg AS (
            SELECT
                innings_id,
                COALESCE(SUM(total_runs), 0)::INT AS total_runs_calculated,
                COUNT(*) FILTER (WHERE is_legal_ball)::INT AS legal_balls_calculated,
                COUNT(*)::INT AS delivery_count
            FROM deliveries
            WHERE match_id = %s
            GROUP BY innings_id
        ),
        wicket_agg AS (
            SELECT
                d.innings_id,
                COUNT(*) FILTER (
                    WHERE LOWER(COALESCE(dw.dismissal_kind, '')) <> 'retired hurt'
                )::INT AS total_wickets_calculated
            FROM delivery_wickets dw
            JOIN deliveries d
              ON d.delivery_id = dw.delivery_id AND d.match_id = dw.match_id
            WHERE dw.match_id = %s
            GROUP BY d.innings_id
        )
        SELECT
            i.match_id,
            i.innings_number,
            i.is_super_over,
            i.total_runs,
            i.total_wickets,
            i.legal_balls_bowled,
            COALESCE(da.total_runs_calculated, 0) AS total_runs_calculated,
            COALESCE(wa.total_wickets_calculated, 0) AS total_wickets_calculated,
            COALESCE(da.legal_balls_calculated, 0) AS legal_balls_calculated,
            COALESCE(da.delivery_count, 0) AS delivery_count
        FROM innings i
        LEFT JOIN delivery_agg da ON da.innings_id = i.innings_id
        LEFT JOIN wicket_agg wa ON wa.innings_id = i.innings_id
        WHERE i.match_id = %s
        ORDER BY i.innings_number ASC;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (match_id, match_id, match_id))
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    summary = validate_all_innings(rows)
    return {
        "match_id": match_id,
        "is_valid": summary["invalid_innings"] == 0,
        **summary,
    }
