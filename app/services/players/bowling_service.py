from typing import Optional

from app.database.connection import get_db_connection
from app.services.players.player_service import resolve_player_sql_filter


def _rows_to_dicts(cursor, rows):
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_player_bowling_stats(player_name: str, season: Optional[str] = None):
    """
    Return bowling statistics for players matching `player_name`,
    optionally filtered by `season`. Super Over innings are excluded.
    """
    if not player_name or not player_name.strip():
        raise ValueError("Player name cannot be empty.")

    if season is not None and (not isinstance(season, str) or not season.strip()):
        raise ValueError("Season must be a non-empty string or None.")

    normalized_season = season.strip() if season else None
    player_predicate, player_params = resolve_player_sql_filter(player_name)

    query = f"""
        WITH matched_players AS (
            SELECT player_id, canonical_name
            FROM players p
            WHERE {player_predicate}
        ),
        bowling AS (
            SELECT
                d.bowler_id AS player_id,
                COUNT(DISTINCT d.match_id) AS matches_bowled,
                COUNT(DISTINCT d.innings_id) AS innings_bowled,
                COUNT(*) FILTER (WHERE d.is_legal_ball = TRUE) AS legal_balls,
                SUM(
                    d.total_runs
                    - d.bye_runs
                    - d.leg_bye_runs
                    - d.penalty_runs
                ) AS runs_conceded
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            WHERE d.bowler_id IN (SELECT player_id FROM matched_players)
              AND i.is_super_over = FALSE
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY d.bowler_id
        ),
        innings_figures AS (
            SELECT
                d.bowler_id AS player_id,
                d.innings_id,
                SUM(
                    d.total_runs
                    - d.bye_runs
                    - d.leg_bye_runs
                    - d.penalty_runs
                ) AS innings_runs,
                COUNT(DISTINCT dw.wicket_id) FILTER (
                    WHERE dw.is_bowler_credit = TRUE
                ) AS innings_wickets
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            LEFT JOIN delivery_wickets dw ON dw.delivery_id = d.delivery_id
            WHERE d.bowler_id IN (SELECT player_id FROM matched_players)
              AND i.is_super_over = FALSE
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY d.bowler_id, d.innings_id
        ),
        wickets AS (
            SELECT
                player_id,
                SUM(innings_wickets) AS wickets,
                COUNT(*) FILTER (WHERE innings_wickets >= 5) AS five_wickets,
                (ARRAY_AGG(
                    CONCAT(innings_wickets, '/', innings_runs)
                    ORDER BY innings_wickets DESC, innings_runs ASC
                ))[1] AS best_bowling
            FROM innings_figures
            GROUP BY player_id
        )
        SELECT
            mp.player_id,
            mp.canonical_name AS player_name,
            COALESCE(b.matches_bowled, 0) AS matches_bowled,
            COALESCE(b.innings_bowled, 0) AS innings_bowled,
            COALESCE(b.legal_balls, 0) AS legal_balls,
            COALESCE(b.runs_conceded, 0) AS runs_conceded,
            COALESCE(w.wickets, 0) AS wickets,
            COALESCE(w.five_wickets, 0) AS five_wickets,
            w.best_bowling,
            CASE
                WHEN COALESCE(b.legal_balls, 0) = 0 THEN 0
                ELSE ROUND(b.runs_conceded::NUMERIC * 6 / b.legal_balls, 2)
            END AS economy,
            CASE
                WHEN COALESCE(w.wickets, 0) = 0 THEN NULL
                ELSE ROUND(b.runs_conceded::NUMERIC / w.wickets, 2)
            END AS bowling_average,
            CASE
                WHEN COALESCE(w.wickets, 0) = 0 THEN NULL
                ELSE ROUND(b.legal_balls::NUMERIC / w.wickets, 2)
            END AS bowling_strike_rate
        FROM matched_players mp
        JOIN bowling b ON b.player_id = mp.player_id
        LEFT JOIN wickets w ON w.player_id = mp.player_id
        ORDER BY wickets DESC, economy ASC;
    """

    params = (
        *player_params,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return _rows_to_dicts(cur, rows)
