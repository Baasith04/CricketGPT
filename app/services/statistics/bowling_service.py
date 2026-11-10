from app.database.connection import get_db_connection


# Shared SQL for player career bowling statistics.
# Super overs are excluded.
# Legal balls are counted from deliveries.is_legal_ball = TRUE.
# Runs conceded includes batter_runs + wide_runs + no_ball_runs (byes, leg-byes, penalty runs excluded).
# Only wickets credited to the bowler (delivery_wickets.is_bowler_credit = TRUE) are counted.
# Maidens require exactly 6 legal balls bowled by that bowler in that over with 0 runs conceded off the bowler.
# Best bowling figures are formatted as W/R and ranked by wickets DESC, runs_conceded ASC.
BOWLING_STATS_QUERY = """
    WITH player_innings AS (
        SELECT
            d.bowler_id AS player_id,
            COALESCE(
                p.canonical_name,
                MAX(d.bowler_name)
            ) AS player_name,
            d.match_id,
            d.innings_id,

            COUNT(*) FILTER (
                WHERE d.is_legal_ball = TRUE
            ) AS legal_balls,

            SUM(
                d.batter_runs
                + COALESCE(d.wide_runs, 0)
                + COALESCE(d.no_ball_runs, 0)
            ) AS runs_conceded,

            COUNT(w.wicket_id) FILTER (
                WHERE w.is_bowler_credit = TRUE
            ) AS wickets

        FROM deliveries d

        JOIN innings i
            ON i.innings_id = d.innings_id

        LEFT JOIN players p
            ON p.player_id = d.bowler_id

        LEFT JOIN delivery_wickets w
            ON w.delivery_id = d.delivery_id

        WHERE d.bowler_id IS NOT NULL
          AND i.is_super_over = FALSE

        GROUP BY
            d.bowler_id,
            p.canonical_name,
            d.match_id,
            d.innings_id
    ),

    over_stats AS (
        SELECT
            d.bowler_id AS player_id,
            d.innings_id,
            d.over_number,

            COUNT(*) FILTER (
                WHERE d.is_legal_ball = TRUE
            ) AS legal_balls,

            SUM(
                d.batter_runs
                + COALESCE(d.wide_runs, 0)
                + COALESCE(d.no_ball_runs, 0)
            ) AS runs_conceded

        FROM deliveries d

        JOIN innings i
            ON i.innings_id = d.innings_id

        WHERE d.bowler_id IS NOT NULL
          AND i.is_super_over = FALSE

        GROUP BY
            d.bowler_id,
            d.innings_id,
            d.over_number
    ),

    player_maidens AS (
        SELECT
            player_id,
            COUNT(*) AS maidens
        FROM over_stats
        WHERE legal_balls = 6
          AND runs_conceded = 0
        GROUP BY player_id
    )

    SELECT
        pi.player_id,
        pi.player_name,
        COUNT(*) AS innings,
        COUNT(DISTINCT pi.match_id) AS matches,
        SUM(pi.legal_balls) AS legal_balls,

        ROUND(
            SUM(pi.legal_balls)::NUMERIC / 6,
            1
        ) AS overs,

        COALESCE(pm.maidens, 0) AS maidens,
        SUM(pi.runs_conceded) AS runs_conceded,
        SUM(pi.wickets) AS wickets,

        ROUND(
            SUM(pi.runs_conceded)::NUMERIC * 6 /
            NULLIF(SUM(pi.legal_balls), 0),
            2
        ) AS economy,

        ROUND(
            SUM(pi.runs_conceded)::NUMERIC /
            NULLIF(SUM(pi.wickets), 0),
            2
        ) AS bowling_average,

        ROUND(
            SUM(pi.legal_balls)::NUMERIC /
            NULLIF(SUM(pi.wickets), 0),
            2
        ) AS bowling_strike_rate,

        (ARRAY_AGG(
            CONCAT(pi.wickets, '/', pi.runs_conceded)
            ORDER BY pi.wickets DESC, pi.runs_conceded ASC
        ))[1] AS best_bowling

    FROM player_innings pi

    LEFT JOIN player_maidens pm
        ON pm.player_id = pi.player_id

    {where_clause}

    GROUP BY
        pi.player_id,
        pi.player_name,
        pm.maidens
"""


BOWLING_COLUMNS = [
    "player_id",
    "player_name",
    "innings",
    "matches",
    "legal_balls",
    "overs",
    "maidens",
    "runs_conceded",
    "wickets",
    "economy",
    "bowling_average",
    "bowling_strike_rate",
    "best_bowling",
]


def _format_bowling_stats(row):
    """Convert a database row into a JSON-friendly dictionary."""

    result = dict(zip(BOWLING_COLUMNS, row))

    for field in (
        "innings",
        "matches",
        "legal_balls",
        "runs_conceded",
        "wickets",
        "maidens",
    ):
        if result.get(field) is not None:
            result[field] = int(result[field])

    for field in (
        "overs",
        "economy",
        "bowling_average",
        "bowling_strike_rate",
    ):
        if result.get(field) is not None:
            result[field] = float(result[field])

    # Provide alias keys for convenience and backward compatibility
    result["best_bowling_figures"] = result.get("best_bowling")
    if result.get("best_bowling"):
        try:
            result["best_innings_wickets"] = int(result["best_bowling"].split("/")[0])
        except (ValueError, IndexError):
            result["best_innings_wickets"] = None
    else:
        result["best_innings_wickets"] = None

    return result


def get_bowling_leaderboard(limit: int = 20):
    """
    Return the top IPL wicket-takers.

    Args:
        limit: Maximum number of players to return (1-100).

    Returns:
        List of player bowling-stat dictionaries.
    """

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Limit must be an integer.")

    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    query = BOWLING_STATS_QUERY.format(
        where_clause=""
    ) + """
        ORDER BY wickets DESC, economy ASC
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        _format_bowling_stats(row)
        for row in rows
    ]


def get_player_bowling_stats(player_id: str):
    """
    Return career IPL bowling statistics for one player.

    Args:
        player_id: Cricsheet registry player ID.

    Returns:
        Dictionary of bowling statistics or None if player not found.
    """

    if not isinstance(player_id, str) or not player_id.strip():
        raise ValueError("Player ID must be a non-empty string.")

    query = BOWLING_STATS_QUERY.format(
        where_clause="WHERE pi.player_id = %s"
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (player_id.strip(),))
            row = cur.fetchone()

    if row is None:
        return None

    return _format_bowling_stats(row)
