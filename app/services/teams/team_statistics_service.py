from typing import Any, Dict, List, Optional, Union

from app.database.connection import get_db_connection


def _resolve_team(team_identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
    """
    Resolve a team by integer ID, numeric string ID, canonical name, short code, or historical alias.
    """
    if team_identifier is None:
        raise ValueError("Team identifier cannot be empty.")

    ident_str = str(team_identifier).strip()
    if not ident_str:
        raise ValueError("Team identifier cannot be empty.")

    # 1. Try resolving by numeric team_id if input is integer or digits
    if isinstance(team_identifier, int) or ident_str.isdigit():
        query_id = """
            SELECT team_id, canonical_name, short_code, is_active
            FROM teams
            WHERE team_id = %s;
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_id, (int(ident_str),))
                row = cur.fetchone()
                if row:
                    return {
                        "team_id": row[0],
                        "team_name": row[1],
                        "short_code": row[2],
                        "is_active": row[3],
                    }

    # 2. Try resolving by canonical name, short code, or alias
    query_name = """
        SELECT team_id, canonical_name, short_code, is_active
        FROM teams t
        WHERE
            t.canonical_name ILIKE %s
            OR t.short_code ILIKE %s
            OR EXISTS (
                SELECT 1
                FROM team_aliases ta
                WHERE ta.team_id = t.team_id
                  AND ta.alias_name ILIKE %s
            )
        ORDER BY t.canonical_name;
    """
    search = f"%{ident_str}%"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query_name, (search, search, search))
            rows = cur.fetchall()

    if not rows:
        return None

    if len(rows) > 1:
        names = ", ".join(r[1] for r in rows)
        raise ValueError(
            f"Ambiguous team '{ident_str}'. Matches: {names}. "
            "Please provide a more specific name or ID."
        )

    return {
        "team_id": rows[0][0],
        "team_name": rows[0][1],
        "short_code": rows[0][2],
        "is_active": rows[0][3],
    }


def get_teams_overall_statistics(active_only: bool = False) -> List[Dict[str, Any]]:
    """
    Return overall IPL match statistics for all teams.
    Includes matches played, wins, losses, ties, no-results, win percentage, and championship titles.
    Avoids join duplication by calculating aggregations in isolated CTEs.
    """
    where_clause = "WHERE t.is_active = TRUE" if active_only else ""

    query = f"""
        WITH match_records AS (
            SELECT
                mt.team_id,
                COUNT(DISTINCT mt.match_id) AS matches_played,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.winner_id = mt.team_id
                ) AS wins,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.winner_id IS NOT NULL AND m.winner_id <> mt.team_id
                ) AS losses,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.result_type = 'tie'
                       OR m.raw_json->'info'->'outcome'->>'result' = 'tie'
                ) AS ties,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.result_type = 'no result'
                      AND COALESCE(m.raw_json->'info'->'outcome'->>'result', '') <> 'tie'
                ) AS no_results
            FROM match_teams mt
            JOIN matches m ON m.match_id = mt.match_id
            GROUP BY mt.team_id
        ),
        season_winners AS (
            SELECT DISTINCT ON (m.season)
                m.season,
                m.winner_id
            FROM matches m
            ORDER BY m.season, m.match_date DESC, m.match_id DESC
        ),
        trophies AS (
            SELECT
                winner_id AS team_id,
                COUNT(*) AS titles
            FROM season_winners
            WHERE winner_id IS NOT NULL
            GROUP BY winner_id
        )
        SELECT
            t.team_id,
            t.canonical_name AS team_name,
            t.short_code,
            t.is_active,
            COALESCE(mr.matches_played, 0) AS matches_played,
            COALESCE(mr.wins, 0) AS wins,
            COALESCE(mr.losses, 0) AS losses,
            COALESCE(mr.ties, 0) AS ties,
            COALESCE(mr.no_results, 0) AS no_results,
            ROUND(
                COALESCE(mr.wins, 0)::NUMERIC * 100 /
                NULLIF(COALESCE(mr.matches_played, 0), 0),
                2
            ) AS win_percentage,
            COALESCE(tr.titles, 0) AS championship_titles
        FROM teams t
        LEFT JOIN match_records mr ON mr.team_id = t.team_id
        LEFT JOIN trophies tr ON tr.team_id = t.team_id
        {where_clause}
        ORDER BY championship_titles DESC, wins DESC, win_percentage DESC, matches_played DESC;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    columns = [
        "team_id",
        "team_name",
        "short_code",
        "is_active",
        "matches_played",
        "wins",
        "losses",
        "ties",
        "no_results",
        "win_percentage",
        "championship_titles",
    ]

    results = []
    for row in rows:
        d = dict(zip(columns, row))
        d["win_percentage"] = (
            float(d["win_percentage"])
            if d["win_percentage"] is not None
            else 0.0
        )
        results.append(d)

    return results


def get_individual_team_statistics(
    team_identifier: Union[int, str],
    season: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return comprehensive career or season-filtered statistics for an individual IPL team.
    Includes overall matches, wins, losses, ties, win percentage,
    non-Super-Over batting and bowling performance stats, and championship seasons.
    """
    team = _resolve_team(team_identifier)
    if not team:
        return None

    team_id = team["team_id"]
    normalized_season = season.strip() if isinstance(season, str) and season.strip() else None

    query = """
        WITH match_records AS (
            SELECT
                mt.team_id,
                COUNT(DISTINCT mt.match_id) AS matches_played,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.winner_id = mt.team_id
                ) AS wins,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.winner_id IS NOT NULL AND m.winner_id <> mt.team_id
                ) AS losses,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.result_type = 'tie'
                       OR m.raw_json->'info'->'outcome'->>'result' = 'tie'
                ) AS ties,
                COUNT(DISTINCT m.match_id) FILTER (
                    WHERE m.result_type = 'no result'
                      AND COALESCE(m.raw_json->'info'->'outcome'->>'result', '') <> 'tie'
                ) AS no_results
            FROM match_teams mt
            JOIN matches m ON m.match_id = mt.match_id
            WHERE mt.team_id = %s
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY mt.team_id
        ),
        batting AS (
            SELECT
                i.batting_team_id AS team_id,
                COUNT(*) AS innings_batted,
                SUM(i.total_runs) AS runs_scored,
                SUM(i.total_wickets) AS wickets_lost,
                SUM(i.legal_balls_bowled) AS legal_balls_faced
            FROM innings i
            JOIN matches m ON m.match_id = i.match_id
            WHERE i.is_super_over = FALSE
              AND i.batting_team_id = %s
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY i.batting_team_id
        ),
        bowling AS (
            SELECT
                i.bowling_team_id AS team_id,
                COUNT(*) AS innings_bowled,
                SUM(i.total_runs) AS runs_conceded,
                SUM(i.total_wickets) AS wickets_taken,
                SUM(i.legal_balls_bowled) AS legal_balls_bowled
            FROM innings i
            JOIN matches m ON m.match_id = i.match_id
            WHERE i.is_super_over = FALSE
              AND i.bowling_team_id = %s
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY i.bowling_team_id
        ),
        season_winners AS (
            SELECT DISTINCT ON (m.season)
                m.season,
                m.winner_id
            FROM matches m
            ORDER BY m.season, m.match_date DESC, m.match_id DESC
        ),
        trophies AS (
            SELECT
                winner_id AS team_id,
                COUNT(*) AS titles,
                ARRAY_AGG(season ORDER BY season) AS seasons
            FROM season_winners
            WHERE winner_id = %s
              AND (%s::varchar IS NULL OR season = %s::varchar)
            GROUP BY winner_id
        )
        SELECT
            t.team_id,
            t.canonical_name AS team_name,
            t.short_code,
            t.is_active,
            COALESCE(mr.matches_played, 0) AS matches_played,
            COALESCE(mr.wins, 0) AS wins,
            COALESCE(mr.losses, 0) AS losses,
            COALESCE(mr.ties, 0) AS ties,
            COALESCE(mr.no_results, 0) AS no_results,
            ROUND(
                COALESCE(mr.wins, 0)::NUMERIC * 100 /
                NULLIF(COALESCE(mr.matches_played, 0), 0),
                2
            ) AS win_percentage,
            COALESCE(b.innings_batted, 0) AS innings_batted,
            COALESCE(b.runs_scored, 0) AS runs_scored,
            COALESCE(b.wickets_lost, 0) AS wickets_lost,
            COALESCE(b.legal_balls_faced, 0) AS legal_balls_faced,
            ROUND(
                COALESCE(b.runs_scored, 0)::NUMERIC * 6 /
                NULLIF(COALESCE(b.legal_balls_faced, 0), 0),
                2
            ) AS batting_run_rate,
            COALESCE(w.innings_bowled, 0) AS innings_bowled,
            COALESCE(w.runs_conceded, 0) AS runs_conceded,
            COALESCE(w.wickets_taken, 0) AS wickets_taken,
            COALESCE(w.legal_balls_bowled, 0) AS legal_balls_bowled,
            ROUND(
                COALESCE(w.runs_conceded, 0)::NUMERIC * 6 /
                NULLIF(COALESCE(w.legal_balls_bowled, 0), 0),
                2
            ) AS bowling_economy,
            COALESCE(tr.titles, 0) AS championship_titles,
            COALESCE(tr.seasons, ARRAY[]::varchar[]) AS championship_seasons
        FROM teams t
        LEFT JOIN match_records mr ON mr.team_id = t.team_id
        LEFT JOIN batting b ON b.team_id = t.team_id
        LEFT JOIN bowling w ON w.team_id = t.team_id
        LEFT JOIN trophies tr ON tr.team_id = t.team_id
        WHERE t.team_id = %s;
    """

    params = (
        team_id, normalized_season, normalized_season,
        team_id, normalized_season, normalized_season,
        team_id, normalized_season, normalized_season,
        team_id, normalized_season, normalized_season,
        team_id,
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()

    if not row:
        return None

    columns = [
        "team_id",
        "team_name",
        "short_code",
        "is_active",
        "matches_played",
        "wins",
        "losses",
        "ties",
        "no_results",
        "win_percentage",
        "innings_batted",
        "runs_scored",
        "wickets_lost",
        "legal_balls_faced",
        "batting_run_rate",
        "innings_bowled",
        "runs_conceded",
        "wickets_taken",
        "legal_balls_bowled",
        "bowling_economy",
        "championship_titles",
        "championship_seasons",
    ]

    res = dict(zip(columns, row))
    res["win_percentage"] = (
        float(res["win_percentage"])
        if res["win_percentage"] is not None
        else 0.0
    )
    res["batting_run_rate"] = (
        float(res["batting_run_rate"])
        if res["batting_run_rate"] is not None
        else 0.0
    )
    res["bowling_economy"] = (
        float(res["bowling_economy"])
        if res["bowling_economy"] is not None
        else 0.0
    )
    res["championship_seasons"] = (
        list(res["championship_seasons"])
        if res["championship_seasons"]
        else []
    )
    return res


def get_team_championships() -> List[Dict[str, Any]]:
    """
    Return the list of IPL championship titles won by season.
    Identifies the season winner from the final match of each season.
    """
    query = """
        WITH final_matches AS (
            SELECT
                m.match_id,
                m.season,
                m.match_date,
                m.winner_id,
                ROW_NUMBER() OVER (
                    PARTITION BY m.season
                    ORDER BY m.match_date DESC, m.match_id DESC
                ) AS rn
            FROM matches m
        )
        SELECT
            fm.season,
            fm.match_id,
            fm.match_date,
            t.team_id,
            t.canonical_name AS winner
        FROM final_matches fm
        JOIN teams t ON t.team_id = fm.winner_id
        WHERE fm.rn = 1
        ORDER BY fm.match_date ASC;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    columns = [
        "season",
        "match_id",
        "match_date",
        "team_id",
        "winner",
    ]

    results = []
    for row in rows:
        d = dict(zip(columns, row))
        if hasattr(d["match_date"], "isoformat"):
            d["match_date"] = d["match_date"].isoformat()
        results.append(d)

    return results


def get_team_head_to_head(team_one: str, team_two: str) -> Dict[str, Any]:
    """
    Return head-to-head match statistics between two teams.
    Correctly accounts for ties (including Super Over deciders) and abandoned matches.
    """
    if not team_one or not team_one.strip():
        raise ValueError("Team one identifier cannot be empty.")
    if not team_two or not team_two.strip():
        raise ValueError("Team two identifier cannot be empty.")

    first = _resolve_team(team_one.strip())
    if not first:
        raise ValueError(f"Team '{team_one}' was not found.")

    second = _resolve_team(team_two.strip())
    if not second:
        raise ValueError(f"Team '{team_two}' was not found.")

    if first["team_id"] == second["team_id"]:
        raise ValueError("Please provide two different teams.")

    query = """
        SELECT
            COUNT(*) AS matches_played,
            COUNT(*) FILTER (
                WHERE m.winner_id = %s
            ) AS team_one_wins,
            COUNT(*) FILTER (
                WHERE m.winner_id = %s
            ) AS team_two_wins,
            COUNT(*) FILTER (
                WHERE m.result_type = 'tie'
                   OR m.raw_json->'info'->'outcome'->>'result' = 'tie'
            ) AS ties,
            COUNT(*) FILTER (
                WHERE m.result_type = 'no result'
                  AND COALESCE(m.raw_json->'info'->'outcome'->>'result', '') <> 'tie'
            ) AS no_results
        FROM matches m
        WHERE EXISTS (
            SELECT 1
            FROM match_teams mt
            WHERE mt.match_id = m.match_id
              AND mt.team_id = %s
        )
        AND EXISTS (
            SELECT 1
            FROM match_teams mt
            WHERE mt.match_id = m.match_id
              AND mt.team_id = %s
        );
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    first["team_id"],
                    second["team_id"],
                    first["team_id"],
                    second["team_id"],
                ),
            )
            row = cur.fetchone()

    return {
        "team_one": first["team_name"],
        "team_two": second["team_name"],
        "matches_played": row[0],
        "team_one_wins": row[1],
        "team_two_wins": row[2],
        "ties": row[3],
        "no_results": row[4],
    }


def _format_victory_margin(
    winner: Optional[str],
    result_type: Optional[str],
    result_method: Optional[str],
    win_by_runs: Optional[int],
    win_by_wickets: Optional[int],
    has_super_over: bool,
    raw_outcome: Any,
) -> tuple[Optional[str], Optional[str], str]:
    """Compute (resolved_winner, victory_margin, result_summary) for a match."""
    is_tie = (
        has_super_over
        or result_type == "tie"
        or (isinstance(raw_outcome, dict) and raw_outcome.get("result") == "tie")
    )

    resolved_winner = winner
    if not resolved_winner and isinstance(raw_outcome, dict):
        eliminator = raw_outcome.get("eliminator")
        if eliminator:
            resolved_winner = eliminator

    if is_tie:
        if resolved_winner:
            return resolved_winner, "Super Over", f"{resolved_winner} won the Super Over"
        return resolved_winner, "Tied", "Match tied"

    if result_type == "no result":
        return None, None, "No result (match abandoned)"

    method_suffix = f" ({result_method})" if result_method else ""

    if resolved_winner and win_by_runs:
        unit = "run" if win_by_runs == 1 else "runs"
        margin = f"{win_by_runs} {unit}{method_suffix}"
        return resolved_winner, margin, f"{resolved_winner} won by {margin}"

    if resolved_winner and win_by_wickets:
        unit = "wicket" if win_by_wickets == 1 else "wickets"
        margin = f"{win_by_wickets} {unit}{method_suffix}"
        return resolved_winner, margin, f"{resolved_winner} won by {margin}"

    if resolved_winner:
        return resolved_winner, None, f"{resolved_winner} won{method_suffix}"

    return None, None, "No result"


def get_team_versus_matches(
    team_one: str,
    team_two: str,
    season: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return all matches played between two teams, optionally filtered by season.
    Matches are returned regardless of team order (team 1 vs team 2 or vice versa).
    """
    if not team_one or not team_one.strip():
        raise ValueError("Team one identifier cannot be empty.")
    if not team_two or not team_two.strip():
        raise ValueError("Team two identifier cannot be empty.")

    first = _resolve_team(team_one.strip())
    if not first:
        raise ValueError(f"Team '{team_one}' was not found.")

    second = _resolve_team(team_two.strip())
    if not second:
        raise ValueError(f"Team '{team_two}' was not found.")

    if first["team_id"] == second["team_id"]:
        raise ValueError("Please provide two different teams.")

    normalized_season = season.strip() if isinstance(season, str) and season.strip() else None

    query = """
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            m.venue,
            m.city,
            m.stage,
            m.result_type,
            m.result_method,
            m.win_by_runs,
            m.win_by_wickets,
            winner.canonical_name AS winner,
            EXISTS (
                SELECT 1
                FROM innings i
                WHERE i.match_id = m.match_id
                  AND i.is_super_over = TRUE
            ) AS has_super_over,
            m.raw_json->'info'->'outcome' AS raw_outcome,
            (
                SELECT STRING_AGG(
                    t.canonical_name,
                    ' vs ' ORDER BY mt.team_number
                )
                FROM match_teams mt
                JOIN teams t ON t.team_id = mt.team_id
                WHERE mt.match_id = m.match_id
            ) AS teams
        FROM matches m
        LEFT JOIN teams winner ON winner.team_id = m.winner_id
        WHERE EXISTS (
            SELECT 1
            FROM match_teams mt
            WHERE mt.match_id = m.match_id
              AND mt.team_id = %s
        )
        AND EXISTS (
            SELECT 1
            FROM match_teams mt
            WHERE mt.match_id = m.match_id
              AND mt.team_id = %s
        )
    """

    params: List[Any] = [first["team_id"], second["team_id"]]
    if normalized_season is not None:
        query += " AND m.season = %s"
        params.append(normalized_season)

    query += " ORDER BY m.match_date ASC, m.match_id ASC;"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    matches: List[Dict[str, Any]] = []
    for row in rows:
        (
            match_id,
            m_season,
            match_date,
            venue,
            city,
            stage,
            result_type,
            result_method,
            win_by_runs,
            win_by_wickets,
            winner,
            has_super_over,
            raw_outcome,
            teams,
        ) = row

        resolved_winner, victory_margin, result_summary = _format_victory_margin(
            winner=winner,
            result_type=result_type,
            result_method=result_method,
            win_by_runs=win_by_runs,
            win_by_wickets=win_by_wickets,
            has_super_over=bool(has_super_over),
            raw_outcome=raw_outcome,
        )

        matches.append(
            {
                "match_id": match_id,
                "season": m_season,
                "match_date": (
                    match_date.isoformat()
                    if hasattr(match_date, "isoformat")
                    else str(match_date)
                ),
                "teams": teams,
                "venue": venue,
                "city": city,
                "stage": stage,
                "winner": resolved_winner,
                "result_type": result_type,
                "result_method": result_method,
                "win_by_runs": win_by_runs,
                "win_by_wickets": win_by_wickets,
                "is_super_over": bool(has_super_over),
                "victory_margin": victory_margin,
                "result_summary": result_summary,
            }
        )

    return {
        "team_one": first["team_name"],
        "team_two": second["team_name"],
        "season": normalized_season,
        "matches": matches,
    }


def get_team_runs_leaderboard(
    season: Optional[str] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """
    Return teams ranked by total runs scored (excluding Super Overs),
    optionally filtered by season.
    """
    normalized_season = season.strip() if isinstance(season, str) and season.strip() else None

    query = """
        SELECT
            t.team_id,
            t.canonical_name AS team_name,
            t.short_code,
            COUNT(DISTINCT i.match_id) AS matches_played,
            COUNT(i.innings_id) AS innings_batted,
            COALESCE(SUM(i.total_runs), 0) AS total_runs,
            COALESCE(SUM(i.total_wickets), 0) AS wickets_lost,
            COALESCE(SUM(i.legal_balls_bowled), 0) AS legal_balls_faced,
            ROUND(
                COALESCE(SUM(i.total_runs), 0)::NUMERIC * 6 /
                NULLIF(COALESCE(SUM(i.legal_balls_bowled), 0), 0),
                2
            ) AS run_rate
        FROM teams t
        JOIN innings i
            ON i.batting_team_id = t.team_id
        JOIN matches m
            ON m.match_id = i.match_id
        WHERE i.is_super_over = FALSE
          AND (%s::varchar IS NULL OR m.season = %s::varchar)
        GROUP BY t.team_id, t.canonical_name, t.short_code
        ORDER BY total_runs DESC, run_rate DESC
        LIMIT %s;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (normalized_season, normalized_season, limit))
            rows = cur.fetchall()
            columns = [col.name for col in cur.description]

    results = []
    for row in rows:
        d = dict(zip(columns, row))
        d["run_rate"] = float(d["run_rate"]) if d["run_rate"] is not None else 0.0
        results.append(d)
    return results


def get_team_statistics(team_name: str) -> Optional[Dict[str, Any]]:
    """Backward-compatible alias for get_individual_team_statistics."""
    return get_individual_team_statistics(team_name)
