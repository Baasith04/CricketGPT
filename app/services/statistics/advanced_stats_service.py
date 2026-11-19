"""
CricketGPT — Advanced Cricket Statistics & Match Query Service

Provides SQL-backed queries for:
- Player season-by-season breakdowns
- Match filtering by date/teams/season, Player of the Match, and final-over ball-by-ball
- Highest successful run chases, biggest victories (runs/wickets), highest/lowest team totals
- Most sixes in an innings
- Phase statistics (powerplay, middle, death overs)
- Extras and dismissal type summaries
"""

from datetime import date
from typing import Any, Dict, List, Optional

from app.database.connection import get_db_connection
from app.services.players.player_service import resolve_player_sql_filter
from app.services.teams.team_statistics_service import (
    _format_victory_margin,
    _resolve_team,
)


def _fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [col.name for col in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_player_season_breakdown(player_name: str) -> Dict[str, Any]:
    """Return season-by-season batting and bowling statistics for a player."""
    if not player_name or not player_name.strip():
        raise ValueError("Player name cannot be empty.")

    player_predicate, player_params = resolve_player_sql_filter(player_name)

    matched = _fetch_all(
        f"SELECT player_id, canonical_name FROM players p WHERE {player_predicate};",
        player_params,
    )
    if not matched:
        return {"player_name": player_name, "seasons": []}

    # Pick the primary match by total appearances if more than one shares substring
    if len(matched) > 1:
        ids = tuple(r["player_id"] for r in matched)
        ranked = _fetch_all(
            """
            SELECT p.player_id, p.canonical_name, COUNT(DISTINCT d.match_id) AS apps
            FROM players p
            LEFT JOIN deliveries d
              ON d.batter_id = p.player_id OR d.bowler_id = p.player_id
            WHERE p.player_id = ANY(%s)
            GROUP BY p.player_id, p.canonical_name
            ORDER BY apps DESC, p.canonical_name ASC
            LIMIT 1;
            """,
            (list(ids),),
        )
        target = ranked[0]
    else:
        target = matched[0]

    player_id = target["player_id"]
    resolved_name = target["canonical_name"]

    query = """
        WITH season_list AS (
            SELECT DISTINCT m.season, MIN(m.match_date) AS first_date
            FROM matches m
            JOIN match_players mp ON mp.match_id = m.match_id
            WHERE mp.player_id = %s
            GROUP BY m.season
        ),
        innings_scores AS (
            SELECT
                m.season,
                d.innings_id,
                SUM(d.batter_runs) AS score
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            WHERE d.batter_id = %s
              AND i.is_super_over = FALSE
            GROUP BY m.season, d.innings_id
        ),
        bat AS (
            SELECT
                m.season,
                COUNT(DISTINCT d.match_id) AS bat_matches,
                COUNT(DISTINCT d.innings_id) AS innings_batted,
                SUM(d.batter_runs) AS runs,
                COUNT(*) FILTER (WHERE d.wide_runs = 0) AS balls_faced,
                COUNT(*) FILTER (WHERE d.batter_runs = 4) AS fours,
                COUNT(*) FILTER (WHERE d.batter_runs = 6) AS sixes
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            WHERE d.batter_id = %s
              AND i.is_super_over = FALSE
            GROUP BY m.season
        ),
        bat_ms AS (
            SELECT season, MAX(score) AS highest_score
            FROM innings_scores
            GROUP BY season
        ),
        dismissals AS (
            SELECT
                m.season,
                COUNT(*) FILTER (WHERE LOWER(dw.dismissal_kind) <> 'retired hurt') AS outs
            FROM delivery_wickets dw
            JOIN deliveries d ON d.delivery_id = dw.delivery_id
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = dw.match_id
            WHERE dw.player_dismissed_id = %s
              AND i.is_super_over = FALSE
            GROUP BY m.season
        ),
        bowl AS (
            SELECT
                m.season,
                COUNT(*) FILTER (WHERE d.is_legal_ball = TRUE) AS legal_balls,
                SUM(d.batter_runs + d.wide_runs + d.no_ball_runs) AS runs_conceded
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            WHERE d.bowler_id = %s
              AND i.is_super_over = FALSE
            GROUP BY m.season
        ),
        wkts AS (
            SELECT
                m.season,
                COUNT(*) FILTER (WHERE dw.is_bowler_credit = TRUE) AS wickets
            FROM delivery_wickets dw
            JOIN deliveries d ON d.delivery_id = dw.delivery_id
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = dw.match_id
            WHERE d.bowler_id = %s
              AND i.is_super_over = FALSE
            GROUP BY m.season
        ),
        match_counts AS (
            SELECT m.season, COUNT(DISTINCT mp.match_id) AS matches
            FROM match_players mp
            JOIN matches m ON m.match_id = mp.match_id
            WHERE mp.player_id = %s
            GROUP BY m.season
        )
        SELECT
            sl.season,
            COALESCE(mc.matches, 0) AS matches,
            COALESCE(b.innings_batted, 0) AS innings_batted,
            COALESCE(b.runs, 0) AS runs,
            COALESCE(b.balls_faced, 0) AS balls_faced,
            COALESCE(bm.highest_score, 0) AS highest_score,
            ROUND(COALESCE(b.runs, 0)::numeric / NULLIF(COALESCE(ds.outs, 0), 0), 2) AS batting_average,
            ROUND(COALESCE(b.runs, 0)::numeric * 100 / NULLIF(COALESCE(b.balls_faced, 0), 0), 2) AS strike_rate,
            COALESCE(b.fours, 0) AS fours,
            COALESCE(b.sixes, 0) AS sixes,
            COALESCE(w.wickets, 0) AS wickets,
            COALESCE(bw.runs_conceded, 0) AS runs_conceded,
            ROUND(COALESCE(bw.runs_conceded, 0)::numeric * 6 / NULLIF(COALESCE(bw.legal_balls, 0), 0), 2) AS economy
        FROM season_list sl
        LEFT JOIN match_counts mc ON mc.season = sl.season
        LEFT JOIN bat b ON b.season = sl.season
        LEFT JOIN bat_ms bm ON bm.season = sl.season
        LEFT JOIN dismissals ds ON ds.season = sl.season
        LEFT JOIN bowl bw ON bw.season = sl.season
        LEFT JOIN wkts w ON w.season = sl.season
        ORDER BY sl.first_date ASC;
    """

    rows = _fetch_all(
        query,
        (player_id, player_id, player_id, player_id, player_id, player_id, player_id),
    )
    return {
        "player_id": player_id,
        "player_name": resolved_name,
        "seasons": rows,
    }


def find_matches_by_filter(
    season: Optional[str] = None,
    team_one: Optional[str] = None,
    team_two: Optional[str] = None,
    match_date: Optional[date] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Find matches filtered by optional date, season, and one or two teams."""
    team_ids: List[int] = []
    for team_ident in (team_one, team_two):
        if team_ident and team_ident.strip():
            resolved = _resolve_team(team_ident.strip())
            if not resolved:
                raise ValueError(f"Team '{team_ident}' was not found.")
            team_ids.append(resolved["team_id"])

    if len(team_ids) == 2 and team_ids[0] == team_ids[1]:
        raise ValueError("Please provide two different teams.")

    query = """
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            m.venue,
            m.city,
            m.result_type,
            m.result_method,
            m.win_by_runs,
            m.win_by_wickets,
            winner.canonical_name AS winner,
            EXISTS (
                SELECT 1 FROM innings i
                WHERE i.match_id = m.match_id AND i.is_super_over = TRUE
            ) AS has_super_over,
            m.raw_json->'info'->'outcome' AS raw_outcome,
            (
                SELECT STRING_AGG(t.canonical_name, ' vs ' ORDER BY mt.team_number)
                FROM match_teams mt
                JOIN teams t ON t.team_id = mt.team_id
                WHERE mt.match_id = m.match_id
            ) AS teams
        FROM matches m
        LEFT JOIN teams winner ON winner.team_id = m.winner_id
        WHERE 1 = 1
    """
    params: List[Any] = []
    if season:
        query += " AND m.season = %s"
        params.append(season.strip())
    if match_date:
        query += " AND m.match_date = %s"
        params.append(match_date)
    for tid in team_ids:
        query += """
            AND EXISTS (
                SELECT 1 FROM match_teams mt
                WHERE mt.match_id = m.match_id AND mt.team_id = %s
            )
        """
        params.append(tid)

    query += " ORDER BY m.match_date ASC, m.match_id ASC LIMIT %s;"
    params.append(limit)

    raw_rows = _fetch_all(query, tuple(params))
    results: List[Dict[str, Any]] = []
    for r in raw_rows:
        winner, margin, summary = _format_victory_margin(
            winner=r["winner"],
            result_type=r["result_type"],
            result_method=r["result_method"],
            win_by_runs=r["win_by_runs"],
            win_by_wickets=r["win_by_wickets"],
            has_super_over=bool(r["has_super_over"]),
            raw_outcome=r["raw_outcome"],
        )
        results.append(
            {
                "match_id": r["match_id"],
                "season": r["season"],
                "match_date": (
                    r["match_date"].isoformat()
                    if hasattr(r["match_date"], "isoformat")
                    else str(r["match_date"])
                ),
                "teams": r["teams"],
                "venue": r["venue"],
                "city": r["city"],
                "winner": winner,
                "victory_margin": margin,
                "result_summary": summary,
            }
        )
    return results


_SINGLE_MATCH_AWARD_SELECT = """
    SELECT
        m.match_id,
        m.season,
        m.match_date,
        COALESCE(
            NULLIF(TRIM(m.stage), ''),
            NULLIF(TRIM(m.raw_json->'info'->'event'->>'stage'), '')
        ) AS stage,
        ma.award_name,
        ma.player_id,
        COALESCE(p.canonical_name, ma.recipient_name) AS player_name,
        pt.canonical_name AS player_team,
        (
            SELECT STRING_AGG(t.canonical_name, ' vs ' ORDER BY mt.team_number)
            FROM match_teams mt
            JOIN teams t ON t.team_id = mt.team_id
            WHERE mt.match_id = m.match_id
        ) AS teams
    FROM match_awards ma
    JOIN matches m ON m.match_id = ma.match_id
    LEFT JOIN players p ON p.player_id = ma.player_id
    LEFT JOIN match_players mp
      ON mp.match_id = m.match_id
     AND mp.player_id = ma.player_id
    LEFT JOIN teams pt ON pt.team_id = mp.team_id
"""


def get_match_awards(
    match_id: Optional[int] = None,
    season: Optional[str] = None,
    final_only: bool = False,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return Player of the Match award(s) for a match, season final, or leaderboard."""
    if match_id is not None:
        return _fetch_all(
            f"""
            {_SINGLE_MATCH_AWARD_SELECT}
            WHERE ma.match_id = %s;
            """,
            (match_id,),
        )

    if final_only and season:
        return _fetch_all(
            f"""
            WITH target_match AS (
                SELECT match_id
                FROM matches
                WHERE season = %s
                ORDER BY
                    CASE
                        WHEN COALESCE(
                            NULLIF(TRIM(stage), ''),
                            NULLIF(TRIM(raw_json->'info'->'event'->>'stage'), '')
                        ) = 'Final' THEN 0
                        ELSE 1
                    END ASC,
                    match_date DESC,
                    match_id DESC
                LIMIT 1
            )
            {_SINGLE_MATCH_AWARD_SELECT}
            JOIN target_match tm ON tm.match_id = m.match_id;
            """,
            (season.strip(),),
        )

    return _fetch_all(
        """
        SELECT
            ma.player_id,
            COALESCE(p.canonical_name, MAX(ma.recipient_name)) AS player_name,
            COUNT(*) AS awards_count
        FROM match_awards ma
        JOIN matches m ON m.match_id = ma.match_id
        LEFT JOIN players p ON p.player_id = ma.player_id
        WHERE (%s::varchar IS NULL OR m.season = %s::varchar)
        GROUP BY ma.player_id, p.canonical_name
        ORDER BY awards_count DESC, player_name ASC
        LIMIT %s;
        """,
        (season, season, limit),
    )


def get_match_last_over(match_id: int) -> Optional[Dict[str, Any]]:
    """Return ball-by-ball details of the final over of a match's deciding innings."""
    if not isinstance(match_id, int) or match_id <= 0:
        raise ValueError("Match ID must be a positive integer.")

    innings_rows = _fetch_all(
        """
        SELECT
            i.innings_id,
            i.innings_number,
            i.is_super_over,
            bt.canonical_name AS batting_team,
            bw.canonical_name AS bowling_team
        FROM innings i
        JOIN teams bt ON bt.team_id = i.batting_team_id
        JOIN teams bw ON bw.team_id = i.bowling_team_id
        WHERE i.match_id = %s
        ORDER BY i.innings_number DESC
        LIMIT 1;
        """,
        (match_id,),
    )
    if not innings_rows:
        return None

    innings = innings_rows[0]
    deliveries = _fetch_all(
        """
        WITH max_over AS (
            SELECT MAX(over_number) AS over_num
            FROM deliveries
            WHERE innings_id = %s
        )
        SELECT
            d.over_number,
            d.delivery_sequence,
            d.batter_name,
            d.bowler_name,
            d.batter_runs,
            d.extra_runs,
            d.total_runs,
            d.wide_runs,
            d.no_ball_runs,
            d.bye_runs,
            d.leg_bye_runs,
            d.penalty_runs,
            (
                SELECT STRING_AGG(
                    dw.dismissal_kind || ' (' || dw.player_dismissed_name || ')',
                    ', '
                )
                FROM delivery_wickets dw
                WHERE dw.delivery_id = d.delivery_id
            ) AS wicket_text
        FROM deliveries d
        JOIN max_over mo ON d.over_number = mo.over_num
        WHERE d.innings_id = %s
        ORDER BY d.delivery_sequence ASC;
        """,
        (innings["innings_id"], innings["innings_id"]),
    )

    return {
        "match_id": match_id,
        "innings_number": innings["innings_number"],
        "is_super_over": innings["is_super_over"],
        "batting_team": innings["batting_team"],
        "bowling_team": innings["bowling_team"],
        "over_number": deliveries[0]["over_number"] + 1 if deliveries else None,
        "deliveries": deliveries,
    }


def get_highest_successful_chases(
    season: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return the highest successful 2nd-innings run chases in IPL history."""
    return _fetch_all(
        """
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            bt.canonical_name AS chasing_team,
            bw.canonical_name AS bowling_team,
            i.total_runs,
            i.total_wickets,
            i.legal_balls_bowled,
            i.target_runs,
            m.win_by_wickets,
            m.venue
        FROM innings i
        JOIN matches m ON m.match_id = i.match_id
        JOIN teams bt ON bt.team_id = i.batting_team_id
        JOIN teams bw ON bw.team_id = i.bowling_team_id
        WHERE i.is_super_over = FALSE
          AND i.innings_number = 2
          AND m.winner_id = i.batting_team_id
          AND (%s::varchar IS NULL OR m.season = %s::varchar)
        ORDER BY i.total_runs DESC, i.total_wickets ASC, m.match_date DESC
        LIMIT %s;
        """,
        (season, season, limit),
    )


def get_biggest_victories(
    by: str = "runs",
    season: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return the biggest IPL victories by runs or by wickets."""
    if by not in ("runs", "wickets"):
        raise ValueError("Victory margin type must be 'runs' or 'wickets'.")

    if by == "runs":
        where_margin = "m.win_by_runs IS NOT NULL"
        order_by = "m.win_by_runs DESC, m.match_date DESC"
    else:
        where_margin = "m.win_by_wickets IS NOT NULL"
        order_by = "m.win_by_wickets DESC, m.match_date DESC"

    query = f"""
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            winner.canonical_name AS winner,
            loser.canonical_name AS opponent,
            m.win_by_runs,
            m.win_by_wickets,
            m.result_method,
            m.venue
        FROM matches m
        JOIN teams winner ON winner.team_id = m.winner_id
        JOIN match_teams mt ON mt.match_id = m.match_id AND mt.team_id <> m.winner_id
        JOIN teams loser ON loser.team_id = mt.team_id
        WHERE {where_margin}
          AND (%s::varchar IS NULL OR m.season = %s::varchar)
        ORDER BY {order_by}
        LIMIT %s;
    """
    return _fetch_all(query, (season, season, limit))


def get_team_totals_records(
    highest: bool = True,
    season: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Return highest or lowest completed IPL team innings totals.
    For lowest totals, restricts to completed all-out or 20-over non-abandoned innings
    so rain-curtailed 5-over matches do not distort genuine lowest totals.
    """
    if highest:
        extra_filter = ""
        order_by = "i.total_runs DESC, i.total_wickets ASC"
    else:
        extra_filter = (
            "AND m.result_type <> 'no result' "
            "AND (i.total_wickets = 10 OR i.legal_balls_bowled >= 120)"
        )
        order_by = "i.total_runs ASC, i.legal_balls_bowled ASC"

    query = f"""
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            bt.canonical_name AS batting_team,
            bw.canonical_name AS bowling_team,
            i.innings_number,
            i.total_runs,
            i.total_wickets,
            i.legal_balls_bowled,
            m.venue
        FROM innings i
        JOIN matches m ON m.match_id = i.match_id
        JOIN teams bt ON bt.team_id = i.batting_team_id
        JOIN teams bw ON bw.team_id = i.bowling_team_id
        WHERE i.is_super_over = FALSE
          AND (%s::varchar IS NULL OR m.season = %s::varchar)
          {extra_filter}
        ORDER BY {order_by}
        LIMIT %s;
    """
    return _fetch_all(query, (season, season, limit))


def get_most_sixes_in_innings(
    season: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return individual batting innings with the most sixes hit."""
    return _fetch_all(
        """
        SELECT
            d.batter_id AS player_id,
            p.canonical_name AS player_name,
            d.match_id,
            m.season,
            m.match_date,
            bt.canonical_name AS batting_team,
            bw.canonical_name AS opponent,
            COUNT(*) FILTER (WHERE d.batter_runs = 6) AS sixes,
            SUM(d.batter_runs) AS runs,
            COUNT(*) FILTER (WHERE d.wide_runs = 0) AS balls_faced
        FROM deliveries d
        JOIN innings i ON i.innings_id = d.innings_id
        JOIN matches m ON m.match_id = d.match_id
        JOIN players p ON p.player_id = d.batter_id
        JOIN teams bt ON bt.team_id = i.batting_team_id
        JOIN teams bw ON bw.team_id = i.bowling_team_id
        WHERE i.is_super_over = FALSE
          AND (%s::varchar IS NULL OR m.season = %s::varchar)
        GROUP BY
            d.batter_id,
            p.canonical_name,
            d.match_id,
            m.season,
            m.match_date,
            bt.canonical_name,
            bw.canonical_name,
            d.innings_id
        HAVING COUNT(*) FILTER (WHERE d.batter_runs = 6) > 0
        ORDER BY sixes DESC, runs DESC, balls_faced ASC
        LIMIT %s;
        """,
        (season, season, limit),
    )


def get_phase_statistics(
    phase: str = "powerplay",
    stat_type: str = "batting",
    season: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Return Powerplay (overs 1-6), Middle (7-15), or Death (16-20) phase stats
    for top batters or bowlers in regular innings.
    Note: deliveries.over_number is 0-indexed (0..5, 6..14, 15..19).
    """
    phase_ranges = {
        "powerplay": (0, 5, "Overs 1-6 (Powerplay)"),
        "middle": (6, 14, "Overs 7-15 (Middle Overs)"),
        "death": (15, 19, "Overs 16-20 (Death Overs)"),
    }
    if phase not in phase_ranges:
        raise ValueError("Phase must be 'powerplay', 'middle', or 'death'.")

    start_over, end_over, label = phase_ranges[phase]

    if stat_type == "bowling":
        rows = _fetch_all(
            """
            WITH phase_balls AS (
                SELECT
                    d.delivery_id,
                    d.bowler_id,
                    d.batter_runs,
                    d.wide_runs,
                    d.no_ball_runs,
                    d.is_legal_ball
                FROM deliveries d
                JOIN innings i ON i.innings_id = d.innings_id
                JOIN matches m ON m.match_id = d.match_id
                WHERE i.is_super_over = FALSE
                  AND d.over_number BETWEEN %s AND %s
                  AND (%s::varchar IS NULL OR m.season = %s::varchar)
            ),
            phase_wickets AS (
                SELECT
                    pb.bowler_id,
                    COUNT(DISTINCT dw.wicket_id) AS wickets
                FROM phase_balls pb
                JOIN delivery_wickets dw ON dw.delivery_id = pb.delivery_id
                WHERE dw.is_bowler_credit = TRUE
                GROUP BY pb.bowler_id
            )
            SELECT
                pb.bowler_id AS player_id,
                p.canonical_name AS player_name,
                COUNT(*) FILTER (WHERE pb.is_legal_ball = TRUE) AS legal_balls,
                SUM(pb.batter_runs + pb.wide_runs + pb.no_ball_runs) AS runs_conceded,
                COALESCE(pw.wickets, 0) AS wickets,
                ROUND(
                    SUM(pb.batter_runs + pb.wide_runs + pb.no_ball_runs)::numeric * 6 /
                    NULLIF(COUNT(*) FILTER (WHERE pb.is_legal_ball = TRUE), 0),
                    2
                ) AS economy
            FROM phase_balls pb
            JOIN players p ON p.player_id = pb.bowler_id
            LEFT JOIN phase_wickets pw ON pw.bowler_id = pb.bowler_id
            GROUP BY pb.bowler_id, p.canonical_name, pw.wickets
            HAVING COUNT(*) FILTER (WHERE pb.is_legal_ball = TRUE) >= 60
            ORDER BY wickets DESC, economy ASC
            LIMIT %s;
            """,
            (start_over, end_over, season, season, limit),
        )
    else:
        rows = _fetch_all(
            """
            SELECT
                d.batter_id AS player_id,
                p.canonical_name AS player_name,
                SUM(d.batter_runs) AS total_runs,
                COUNT(*) FILTER (WHERE d.wide_runs = 0) AS balls_faced,
                COUNT(*) FILTER (WHERE d.batter_runs = 4) AS fours,
                COUNT(*) FILTER (WHERE d.batter_runs = 6) AS sixes,
                ROUND(
                    SUM(d.batter_runs)::numeric * 100 /
                    NULLIF(COUNT(*) FILTER (WHERE d.wide_runs = 0), 0),
                    2
                ) AS strike_rate
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            JOIN players p ON p.player_id = d.batter_id
            WHERE i.is_super_over = FALSE
              AND d.over_number BETWEEN %s AND %s
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY d.batter_id, p.canonical_name
            HAVING COUNT(*) FILTER (WHERE d.wide_runs = 0) >= 60
            ORDER BY total_runs DESC, strike_rate DESC
            LIMIT %s;
            """,
            (start_over, end_over, season, season, limit),
        )

    return {
        "phase": phase,
        "phase_label": label,
        "stat_type": stat_type,
        "season": season,
        "rows": rows,
    }


def get_extras_and_dismissals_summary(season: Optional[str] = None) -> Dict[str, Any]:
    """Return breakdown of extras and dismissal kinds across regular IPL innings."""
    extras = _fetch_all(
        """
        SELECT
            COUNT(*) AS total_deliveries,
            COALESCE(SUM(d.extra_runs), 0) AS total_extras,
            COALESCE(SUM(d.wide_runs), 0) AS wide_runs,
            COALESCE(SUM(d.no_ball_runs), 0) AS no_ball_runs,
            COALESCE(SUM(d.leg_bye_runs), 0) AS leg_bye_runs,
            COALESCE(SUM(d.bye_runs), 0) AS bye_runs,
            COALESCE(SUM(d.penalty_runs), 0) AS penalty_runs
        FROM deliveries d
        JOIN innings i ON i.innings_id = d.innings_id
        JOIN matches m ON m.match_id = d.match_id
        WHERE i.is_super_over = FALSE
          AND (%s::varchar IS NULL OR m.season = %s::varchar);
        """,
        (season, season),
    )[0]

    dismissals = _fetch_all(
        """
        SELECT
            dw.dismissal_kind,
            COUNT(*) AS total_count,
            dw.is_bowler_credit
        FROM delivery_wickets dw
        JOIN deliveries d ON d.delivery_id = dw.delivery_id
        JOIN innings i ON i.innings_id = d.innings_id
        JOIN matches m ON m.match_id = dw.match_id
        WHERE i.is_super_over = FALSE
          AND (%s::varchar IS NULL OR m.season = %s::varchar)
        GROUP BY dw.dismissal_kind, dw.is_bowler_credit
        ORDER BY total_count DESC;
        """,
        (season, season),
    )

    return {
        "season": season,
        "extras": extras,
        "dismissals": dismissals,
    }

