from typing import Any, Dict, Optional
from app.database.connection import get_db_connection
from app.services.teams.team_statistics_service import (
    get_team_championships,
)


def get_match_result(match_id: int):
    """Retrieve a basic match result from the database."""
    query = """
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            winner.canonical_name AS winner,
            m.result_type,
            m.win_by_runs,
            m.win_by_wickets,
            m.result_method
        FROM matches AS m
        LEFT JOIN teams AS winner
            ON m.winner_id = winner.team_id
        WHERE m.match_id = %s;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (match_id,))
            row = cur.fetchone()

    if row is None:
        return None

    columns = [
        "match_id",
        "season",
        "match_date",
        "winner",
        "result_type",
        "win_by_runs",
        "win_by_wickets",
        "result_method",
    ]

    return dict(zip(columns, row))


def get_first_match_id():
    """Retrieve the earliest IPL match from the database."""
    query = """
        SELECT match_id
        FROM matches
        ORDER BY match_date ASC, match_id ASC
        LIMIT 1;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()

    return row[0] if row else None



def get_season_winner(season: str):
    """Retrieve the IPL champion for the requested season."""

    if not isinstance(season, str) or not season.strip():
        raise ValueError("Season must be a non-empty string.")

    requested_season = season.strip()

    from app.services.teams.team_statistics_service import get_team_championships

    championships = get_team_championships()

    for championship in championships:
        if str(championship["season"]).strip() == requested_season:
            return {
                "match_id": championship["match_id"],
                "season": championship["season"],
                "match_date": championship["match_date"],
                "stage": "Final",
                "winner": championship["winner"],
                "result_type": None,
                "result_method": None,
            }

    return None



def get_match_details(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve comprehensive match information: venue, date, toss, participating teams, and result.
    """
    if not isinstance(match_id, int) or isinstance(match_id, bool) or match_id <= 0:
        raise ValueError("A valid positive integer match ID is required.")

    query_match = """
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            m.venue,
            m.city,
            m.stage,
            m.toss_winner_id,
            t_toss.canonical_name AS toss_winner_name,
            m.toss_decision,
            m.winner_id,
            t_win.canonical_name AS winner_name,
            m.result_type,
            m.result_method,
            m.win_by_runs,
            m.win_by_wickets,
            EXISTS (
                SELECT 1
                FROM innings i
                WHERE i.match_id = m.match_id AND i.is_super_over = TRUE
            ) AS has_super_over,
            m.raw_json->'info'->'outcome' AS raw_outcome
        FROM matches m
        LEFT JOIN teams t_toss ON t_toss.team_id = m.toss_winner_id
        LEFT JOIN teams t_win ON t_win.team_id = m.winner_id
        WHERE m.match_id = %s;
    """

    query_teams = """
        SELECT
            mt.team_number,
            t.team_id,
            t.canonical_name AS team_name,
            t.short_code,
            mt.original_team_name
        FROM match_teams mt
        JOIN teams t ON t.team_id = mt.team_id
        WHERE mt.match_id = %s
        ORDER BY mt.team_number ASC;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query_match, (match_id,))
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(query_teams, (match_id,))
            team_rows = cur.fetchall()

    (
        m_id, season, match_date, venue, city, stage,
        toss_winner_id, toss_winner_name, toss_decision,
        winner_id, winner_name,
        result_type, result_method, win_by_runs, win_by_wickets,
        has_super_over, raw_outcome
    ) = row

    # Handle Cricsheet Super Over eliminator outcome if winner_id was not set
    if not winner_id and isinstance(raw_outcome, dict):
        eliminator_team = raw_outcome.get("eliminator")
        if eliminator_team:
            winner_name = eliminator_team

    # Construct result summary
    if has_super_over or result_type == "tie":
        if winner_name:
            summary = f"{winner_name} won the Super Over (one-over eliminator)"
        else:
            summary = "Match tied"
    elif result_type == "no result":
        summary = "No result (match abandoned)"
    elif winner_name:
        if win_by_runs:
            summary = f"{winner_name} won by {win_by_runs} runs"
        elif win_by_wickets:
            summary = f"{winner_name} won by {win_by_wickets} wickets"
        else:
            summary = f"{winner_name} won"
    else:
        summary = "No result"

    teams = [
        {
            "team_number": t_row[0],
            "team_id": t_row[1],
            "team_name": t_row[2],
            "short_code": t_row[3],
            "original_team_name": t_row[4],
        }
        for t_row in team_rows
    ]

    return {
        "match_id": m_id,
        "season": season,
        "match_date": match_date.isoformat() if hasattr(match_date, "isoformat") else str(match_date),
        "venue": venue,
        "city": city,
        "stage": stage,
        "teams": teams,
        "toss": {
            "toss_winner_id": toss_winner_id,
            "toss_winner_name": toss_winner_name,
            "toss_decision": toss_decision,
        },
        "result": {
            "result_type": result_type,
            "result_method": result_method,
            "winner_id": winner_id,
            "winner_name": winner_name,
            "win_by_runs": win_by_runs,
            "win_by_wickets": win_by_wickets,
            "is_super_over": bool(has_super_over),
            "summary": summary,
        },
    }


def get_latest_season() -> Optional[str]:
    """Return the most recent IPL season present in Supabase."""
    query = """
        SELECT season
        FROM matches
        ORDER BY match_date DESC, match_id DESC
        LIMIT 1;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
    return str(row[0]).strip() if row and row[0] is not None else None
