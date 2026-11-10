from app.database.connection import get_db_connection


def _rows_to_dicts(cursor, rows):
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_player_bowling_stats(player_name: str):
    if not player_name or not player_name.strip():
        raise ValueError("Player name cannot be empty.")

    query = """
        WITH bowling AS (
            SELECT
                d.bowler_id AS player_id,
                COUNT(DISTINCT d.match_id) AS matches_bowled,
                COUNT(DISTINCT d.innings_id) AS innings_bowled,
                COUNT(*) FILTER (
                    WHERE d.is_legal_ball = TRUE
                ) AS legal_balls,
                SUM(
                    d.total_runs
                    - d.bye_runs
                    - d.leg_bye_runs
                    - d.penalty_runs
                ) AS runs_conceded
            FROM deliveries d
            WHERE d.bowler_id IN (
                SELECT player_id
                FROM players
                WHERE canonical_name ILIKE %s
            )
            GROUP BY d.bowler_id
        ),
        wickets AS (
            SELECT
                d.bowler_id AS player_id,
                COUNT(*) FILTER (
                    WHERE w.is_bowler_credit = TRUE
                ) AS wickets
            FROM deliveries d
            JOIN delivery_wickets w
              ON w.delivery_id = d.delivery_id
             AND w.match_id = d.match_id
            WHERE d.bowler_id IN (
                SELECT player_id
                FROM players
                WHERE canonical_name ILIKE %s
            )
            GROUP BY d.bowler_id
        )
        SELECT
            p.player_id,
            p.canonical_name AS player_name,
            COALESCE(b.matches_bowled, 0) AS matches_bowled,
            COALESCE(b.innings_bowled, 0) AS innings_bowled,
            COALESCE(b.legal_balls, 0) AS legal_balls,
            COALESCE(b.runs_conceded, 0) AS runs_conceded,
            COALESCE(w.wickets, 0) AS wickets,
            CASE
                WHEN COALESCE(b.legal_balls, 0) = 0 THEN 0
                ELSE ROUND(
                    b.runs_conceded::NUMERIC * 6 / b.legal_balls,
                    2
                )
            END AS economy,
            CASE
                WHEN COALESCE(w.wickets, 0) = 0 THEN NULL
                ELSE ROUND(
                    b.runs_conceded::NUMERIC / w.wickets,
                    2
                )
            END AS bowling_average,
            CASE
                WHEN COALESCE(w.wickets, 0) = 0 THEN NULL
                ELSE ROUND(
                    b.legal_balls::NUMERIC / w.wickets,
                    2
                )
            END AS bowling_strike_rate
        FROM players p
        JOIN bowling b ON b.player_id = p.player_id
        LEFT JOIN wickets w ON w.player_id = p.player_id
        WHERE p.canonical_name ILIKE %s
        ORDER BY wickets DESC, economy ASC;
    """

    search = f"%{player_name.strip()}%"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (search, search, search))
            rows = cur.fetchall()
            return _rows_to_dicts(cur, rows)