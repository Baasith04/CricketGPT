
from app.database.connection import get_db_connection


# Shared SQL for player career batting statistics.
# Super overs are excluded.
# Wides are excluded from balls faced; no-balls are included.
# Retired hurt is excluded from dismissals.
BATTING_STATS_QUERY = """
    WITH player_innings AS (
        SELECT
            d.batter_id AS player_id,
            COALESCE(
                p.canonical_name,
                MAX(d.batter_name)
            ) AS player_name,
            d.match_id,
            d.innings_id,

            SUM(d.batter_runs) AS runs,

            COUNT(*) FILTER (
                WHERE COALESCE(d.wide_runs, 0) = 0
            ) AS balls_faced,

            COUNT(*) FILTER (
                WHERE d.batter_runs = 4
            ) AS fours,

            COUNT(*) FILTER (
                WHERE d.batter_runs = 6
            ) AS sixes,

            COALESCE(
                BOOL_OR(
                    w.player_dismissed_id = d.batter_id
                    AND w.dismissal_kind <> 'retired hurt'
                ),
                FALSE
            ) AS is_out

        FROM deliveries d

        JOIN innings i
            ON i.innings_id = d.innings_id

        LEFT JOIN players p
            ON p.player_id = d.batter_id

        LEFT JOIN delivery_wickets w
            ON w.delivery_id = d.delivery_id
           AND w.player_dismissed_id = d.batter_id

        WHERE d.batter_id IS NOT NULL
          AND i.is_super_over = FALSE

        GROUP BY
            d.batter_id,
            p.canonical_name,
            d.match_id,
            d.innings_id
    )

    SELECT
        player_id,
        player_name,
        COUNT(*) AS innings,
        COUNT(DISTINCT match_id) AS matches,
        SUM(runs) AS total_runs,

        COUNT(*) FILTER (
            WHERE NOT is_out
        ) AS not_outs,

        ROUND(
            SUM(runs)::NUMERIC /
            NULLIF(
                COUNT(*) FILTER (WHERE is_out),
                0
            ),
            2
        ) AS batting_average,

        SUM(balls_faced) AS balls_faced,

        ROUND(
            SUM(runs)::NUMERIC * 100 /
            NULLIF(SUM(balls_faced), 0),
            2
        ) AS strike_rate,

        SUM(fours) AS fours,
        SUM(sixes) AS sixes,

        COUNT(*) FILTER (
            WHERE runs >= 50 AND runs < 100
        ) AS fifties,

        COUNT(*) FILTER (
            WHERE runs >= 100
        ) AS hundreds,

        MAX(runs) AS highest_score

    FROM player_innings

    {where_clause}

    GROUP BY player_id, player_name
"""


COLUMNS = [
    "player_id",
    "player_name",
    "innings",
    "matches",
    "total_runs",
    "not_outs",
    "batting_average",
    "balls_faced",
    "strike_rate",
    "fours",
    "sixes",
    "fifties",
    "hundreds",
    "highest_score",
]


def _format_batting_stats(row):
    """Convert a database row into a JSON-friendly dictionary."""

    result = dict(zip(COLUMNS, row))

    # Convert Decimal values returned by PostgreSQL.
    for field in ("batting_average", "strike_rate"):
        if result[field] is not None:
            result[field] = float(result[field])

    return result


def get_batting_leaderboard(limit: int = 20):
    """
    Return the top IPL run scorers.

    Args:
        limit: Maximum number of players to return (1–100).

    Returns:
        List of player batting-stat dictionaries.
    """

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Limit must be an integer.")

    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    query = BATTING_STATS_QUERY.format(
        where_clause=""
    ) + """
        ORDER BY total_runs DESC
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        _format_batting_stats(row)
        for row in rows
    ]



def get_player_batting_stats(player_id: str):
    """
    Return career IPL batting statistics for one player.
    """

    if not isinstance(player_id, str) or not player_id.strip():
        raise ValueError("Player ID must be a non-empty string.")

    query = BATTING_STATS_QUERY.format(
        where_clause="WHERE player_id = %s"
    )

    # The shared query already contains GROUP BY.
    # Do not append another GROUP BY clause.

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (player_id.strip(),))
            row = cur.fetchone()

    if row is None:
        return None

    return _format_batting_stats(row)

