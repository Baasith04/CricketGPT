from app.database.connection import get_db_connection


def _rows_to_dicts(cursor, rows):
    """Convert database rows into dictionaries."""
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_player_batting_stats(player_name: str):
    if not player_name or not player_name.strip():
        raise ValueError("Player name cannot be empty.")

    query = """
        WITH batting AS (
            SELECT
                d.batter_id AS player_id,
                COUNT(DISTINCT d.match_id) AS batting_matches,
                COUNT(DISTINCT d.innings_id) AS innings_batted,
                SUM(d.batter_runs) AS total_runs,
                COUNT(*) FILTER (
                    WHERE d.wide_runs = 0
                ) AS balls_faced,
                MAX(innings_scores.innings_runs) AS highest_score
            FROM deliveries d
            LEFT JOIN LATERAL (
                SELECT SUM(d2.batter_runs) AS innings_runs
                FROM deliveries d2
                WHERE d2.innings_id = d.innings_id
                  AND d2.batter_id = d.batter_id
            ) innings_scores ON TRUE
            WHERE d.batter_id IN (
                SELECT player_id
                FROM players
                WHERE canonical_name ILIKE %s
            )
            GROUP BY d.batter_id
        ),
        dismissals AS (
            SELECT
                player_dismissed_id AS player_id,
                COUNT(*) FILTER (
                    WHERE LOWER(dismissal_kind) <> 'retired hurt'
                ) AS dismissals
            FROM delivery_wickets
            WHERE player_dismissed_id IN (
                SELECT player_id
                FROM players
                WHERE canonical_name ILIKE %s
            )
            GROUP BY player_dismissed_id
        ),
        appearances AS (
            SELECT player_id, COUNT(DISTINCT match_id) AS matches_played
            FROM (
                SELECT batter_id AS player_id, match_id FROM deliveries
                UNION
                SELECT bowler_id AS player_id, match_id FROM deliveries
                UNION
                SELECT non_striker_id AS player_id, match_id FROM deliveries
                UNION
                SELECT player_dismissed_id AS player_id, match_id
                FROM delivery_wickets
            ) participants
            WHERE player_id IN (
                SELECT player_id
                FROM players
                WHERE canonical_name ILIKE %s
            )
            GROUP BY player_id
        )
        SELECT
            p.player_id,
            p.canonical_name AS player_name,
            COALESCE(a.matches_played, 0) AS matches_played,
            COALESCE(b.innings_batted, 0) AS innings_batted,
            COALESCE(b.total_runs, 0) AS total_runs,
            COALESCE(b.highest_score, 0) AS highest_score,
            COALESCE(b.balls_faced, 0) AS balls_faced,
            COALESCE(ds.dismissals, 0) AS dismissals,
            CASE
                WHEN COALESCE(ds.dismissals, 0) = 0 THEN NULL
                ELSE ROUND(
                    b.total_runs::NUMERIC / ds.dismissals,
                    2
                )
            END AS batting_average,
            CASE
                WHEN COALESCE(b.balls_faced, 0) = 0 THEN 0
                ELSE ROUND(
                    b.total_runs::NUMERIC * 100 / b.balls_faced,
                    2
                )
            END AS strike_rate
        FROM players p
        LEFT JOIN batting b ON b.player_id = p.player_id
        LEFT JOIN dismissals ds ON ds.player_id = p.player_id
        LEFT JOIN appearances a ON a.player_id = p.player_id
        WHERE p.canonical_name ILIKE %s
        ORDER BY total_runs DESC, p.canonical_name;
    """

    search = f"%{player_name.strip()}%"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (search, search, search, search))
            rows = cur.fetchall()
            return _rows_to_dicts(cur, rows)