
from app.database.connection import get_db_connection


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

def _validate_season(season):
    if season is not None:
        if not isinstance(season, str) or not season.strip():
            raise ValueError("Season must be a non-empty string or None.")



def _validate_min_balls(min_balls):
    if (
        isinstance(min_balls, bool)
        or not isinstance(min_balls, int)
        or min_balls < 0
    ):
        raise ValueError("Minimum balls must be a non-negative integer.")


def _fetch_all(query, params):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [column.name for column in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


BATTING_ORDER = {
    "runs": "total_runs DESC, player_name ASC",
    "highest_score": "highest_score DESC, total_runs DESC",
    "sixes": "sixes DESC, total_runs DESC",
    "fours": "fours DESC, total_runs DESC",
    "average": "batting_average DESC, total_runs DESC",
    "strike_rate": "strike_rate DESC, total_runs DESC",
}


def get_batting_leaderboard(
    category="runs",
    season=None,
    limit=10,
    min_balls=0,
):
    """
    Return an IPL batting leaderboard.

    Categories:
    runs, highest_score, sixes, fours, average, strike_rate.
    """

    _validate_limit(limit)
    _validate_season(season)
    _validate_min_balls(min_balls)

    if category not in BATTING_ORDER:
        raise ValueError(f"Unsupported batting category: {category}")

    order_by = BATTING_ORDER[category]

    query = f"""
        WITH filtered_deliveries AS (
            SELECT
                d.delivery_id,
                d.match_id,
                d.innings_id,
                d.batter_id,
                d.batter_runs,
                d.wide_runs
            FROM deliveries d
            JOIN matches m
                ON m.match_id = d.match_id
            JOIN innings i
                ON i.innings_id = d.innings_id
            WHERE
                (%s::varchar IS NULL OR m.season = %s::varchar)
                AND i.is_super_over = FALSE
        ),

        batting AS (
            SELECT
                d.batter_id AS player_id,
                p.canonical_name AS player_name,
                COUNT(DISTINCT d.match_id) AS matches_played,
                COUNT(DISTINCT d.innings_id) AS innings_batted,
                SUM(d.batter_runs) AS total_runs,

                COUNT(*) FILTER (
                    WHERE d.wide_runs = 0
                ) AS balls_faced,

                COUNT(*) FILTER (
                    WHERE d.batter_runs = 4
                ) AS fours,

                COUNT(*) FILTER (
                    WHERE d.batter_runs = 6
                ) AS sixes

            FROM filtered_deliveries d
            JOIN players p
                ON p.player_id = d.batter_id
            GROUP BY
                d.batter_id,
                p.canonical_name
        ),

        dismissals AS (
            SELECT
                dw.player_dismissed_id AS player_id,
                COUNT(DISTINCT dw.wicket_id) AS dismissals
            FROM delivery_wickets dw
            JOIN matches m
                ON m.match_id = dw.match_id
            JOIN innings i
                ON i.match_id = dw.match_id
            JOIN deliveries d
                ON d.delivery_id = dw.delivery_id
                AND d.innings_id = i.innings_id
            WHERE
                (%s::varchar IS NULL OR m.season = %s::varchar)
                AND i.is_super_over = FALSE
            GROUP BY dw.player_dismissed_id
        ),

        innings_scores AS (
            SELECT
                d.batter_id AS player_id,
                d.match_id,
                d.innings_id,
                SUM(d.batter_runs) AS innings_score
            FROM filtered_deliveries d
            GROUP BY
                d.batter_id,
                d.match_id,
                d.innings_id
        ),

        highest_scores AS (
            SELECT
                player_id,
                MAX(innings_score) AS highest_score
            FROM innings_scores
            GROUP BY player_id
        )

        SELECT
            b.player_id,
            b.player_name,
            b.matches_played,
            b.innings_batted,
            b.total_runs,
            COALESCE(h.highest_score, 0) AS highest_score,
            b.balls_faced,
            b.fours,
            b.sixes,
            COALESCE(ds.dismissals, 0) AS dismissals,

            CASE
                WHEN COALESCE(ds.dismissals, 0) > 0
                THEN ROUND(
                    b.total_runs::numeric / ds.dismissals,
                    2
                )
                ELSE NULL
            END AS batting_average,

            CASE
                WHEN b.balls_faced > 0
                THEN ROUND(
                    b.total_runs::numeric * 100 / b.balls_faced,
                    2
                )
                ELSE NULL
            END AS strike_rate

        FROM batting b
        LEFT JOIN dismissals ds
            ON ds.player_id = b.player_id
        LEFT JOIN highest_scores h
            ON h.player_id = b.player_id
        WHERE b.balls_faced >= %s
        ORDER BY {order_by}
        LIMIT %s
    """

    return _fetch_all(
        query,
        (season, season, season, season, min_balls, limit),
    )


BOWLING_ORDER = {
    "wickets": "wickets DESC, runs_conceded ASC",
    "economy": "economy ASC NULLS LAST, wickets DESC",
    "average": "bowling_average ASC NULLS LAST, wickets DESC",
    "strike_rate": "bowling_strike_rate ASC NULLS LAST, wickets DESC",
}


def get_bowling_leaderboard(
    category="wickets",
    season=None,
    limit=10,
    min_balls=0,
):
    """
    Return an IPL bowling leaderboard.

    Categories:
    wickets, economy, average, strike_rate.
    """

    _validate_limit(limit)
    _validate_season(season)
    _validate_min_balls(min_balls)

    if category not in BOWLING_ORDER:
        raise ValueError(f"Unsupported bowling category: {category}")

    order_by = BOWLING_ORDER[category]

    query = f"""
        WITH filtered_deliveries AS (
            SELECT
                d.delivery_id,
                d.match_id,
                d.innings_id,
                d.bowler_id,
                d.total_runs,
                d.bye_runs,
                d.leg_bye_runs,
                d.penalty_runs,
                d.is_legal_ball
            FROM deliveries d
            JOIN matches m
                ON m.match_id = d.match_id
            JOIN innings i
                ON i.innings_id = d.innings_id
            WHERE
                (%s::varchar IS NULL OR m.season = %s::varchar)
                AND i.is_super_over = FALSE
        ),

        bowling AS (
            SELECT
                d.bowler_id AS player_id,
                p.canonical_name AS player_name,
                COUNT(DISTINCT d.match_id) AS matches_played,
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

            FROM filtered_deliveries d
            JOIN players p
                ON p.player_id = d.bowler_id
            GROUP BY
                d.bowler_id,
                p.canonical_name
        ),

        wickets AS (
            SELECT
                d.bowler_id AS player_id,
                COUNT(DISTINCT dw.wicket_id) AS wickets
            FROM filtered_deliveries d
            JOIN delivery_wickets dw
                ON dw.delivery_id = d.delivery_id
            WHERE dw.is_bowler_credit = TRUE
            GROUP BY d.bowler_id
        )

        SELECT
            b.player_id,
            b.player_name,
            b.matches_played,
            b.innings_bowled,
            b.legal_balls,
            b.runs_conceded,
            COALESCE(w.wickets, 0) AS wickets,

            (
                b.legal_balls / 6
                + (b.legal_balls %% 6)::numeric / 10
            ) AS overs,

            CASE
                WHEN b.legal_balls > 0
                THEN ROUND(
                    b.runs_conceded::numeric * 6 / b.legal_balls,
                    2
                )
                ELSE NULL
            END AS economy,

            CASE
                WHEN COALESCE(w.wickets, 0) > 0
                THEN ROUND(
                    b.runs_conceded::numeric / w.wickets,
                    2
                )
                ELSE NULL
            END AS bowling_average,

            CASE
                WHEN COALESCE(w.wickets, 0) > 0
                THEN ROUND(
                    b.legal_balls::numeric / w.wickets,
                    2
                )
                ELSE NULL
            END AS bowling_strike_rate

        FROM bowling b
        LEFT JOIN wickets w
            ON w.player_id = b.player_id
        WHERE b.legal_balls >= %s
        ORDER BY {order_by}
        LIMIT %s
    """

    return _fetch_all(
        query,
        (season, season, min_balls, limit),
    )


def get_best_bowling_figures(season=None, limit=10):
    """Return the best bowling figures in individual innings."""

    _validate_limit(limit)
    _validate_season(season)

    query = """
        WITH filtered_deliveries AS (
            SELECT
                d.delivery_id,
                d.match_id,
                d.innings_id,
                d.bowler_id,
                d.total_runs,
                d.bye_runs,
                d.leg_bye_runs,
                d.penalty_runs,
                d.is_legal_ball
            FROM deliveries d
            JOIN matches m
                ON m.match_id = d.match_id
            JOIN innings i
                ON i.innings_id = d.innings_id
            WHERE
                (%s::varchar IS NULL OR m.season = %s::varchar)
                AND i.is_super_over = FALSE
        ),

        figures AS (
            SELECT
                d.bowler_id AS player_id,
                p.canonical_name AS player_name,
                d.match_id,
                d.innings_id,

                COUNT(*) FILTER (
                    WHERE d.is_legal_ball = TRUE
                ) AS legal_balls,

                SUM(
                    d.total_runs
                    - d.bye_runs
                    - d.leg_bye_runs
                    - d.penalty_runs
                ) AS runs_conceded

            FROM filtered_deliveries d
            JOIN players p
                ON p.player_id = d.bowler_id
            GROUP BY
                d.bowler_id,
                p.canonical_name,
                d.match_id,
                d.innings_id
        ),

        wicket_counts AS (
            SELECT
                d.bowler_id AS player_id,
                d.match_id,
                d.innings_id,
                COUNT(DISTINCT dw.wicket_id) AS wickets
            FROM filtered_deliveries d
            JOIN delivery_wickets dw
                ON dw.delivery_id = d.delivery_id
            WHERE dw.is_bowler_credit = TRUE
            GROUP BY
                d.bowler_id,
                d.match_id,
                d.innings_id
        )

        SELECT
            f.player_id,
            f.player_name,
            f.match_id,
            m.season,
            f.innings_id,
            COALESCE(w.wickets, 0) AS wickets,
            f.runs_conceded,
            f.legal_balls

        FROM figures f
        JOIN matches m
            ON m.match_id = f.match_id
        LEFT JOIN wicket_counts w
            ON w.player_id = f.player_id
            AND w.match_id = f.match_id
            AND w.innings_id = f.innings_id

        ORDER BY
            COALESCE(w.wickets, 0) DESC,
            f.runs_conceded ASC,
            f.legal_balls ASC

        LIMIT %s
    """

    return _fetch_all(query, (season, season, limit))
