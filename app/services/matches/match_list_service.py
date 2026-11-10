from app.database.connection import get_db_connection


def get_matches(
    season: str = None,
    team_name: str = None,
    start_date=None,
    end_date=None,
    limit: int = 20,
    offset: int = 0,
):
    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100.")

    if offset < 0:
        raise ValueError("Offset cannot be negative.")

    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    query = """
        SELECT
            m.match_id,
            m.season,
            m.match_date,
            m.venue,
            m.city,
            m.result_type,
            m.win_by_runs,
            m.win_by_wickets,
            winner.canonical_name AS winner,
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
        LEFT JOIN teams winner
            ON winner.team_id = m.winner_id
        WHERE 1 = 1
    """

    params = []

    if season:
        query += " AND m.season = %s"
        params.append(season)

    if start_date:
        query += " AND m.match_date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND m.match_date <= %s"
        params.append(end_date)

    if team_name:
        query += """
            AND EXISTS (
                SELECT 1
                FROM match_teams mt
                JOIN teams t ON t.team_id = mt.team_id
                WHERE mt.match_id = m.match_id
                  AND (
                    t.canonical_name ILIKE %s
                    OR t.short_code ILIKE %s
                    OR EXISTS (
                        SELECT 1
                        FROM team_aliases ta
                        WHERE ta.team_id = t.team_id
                          AND ta.alias_name ILIKE %s
                    )
                  )
            )
        """
        search = f"%{team_name.strip()}%"
        params.extend([search, search, search])

    query += """
        ORDER BY m.match_date DESC, m.match_id DESC
        LIMIT %s OFFSET %s;
    """

    params.extend([limit, offset])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            columns = [col.name for col in cur.description]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]


def get_match_by_id(match_id: int):
    from app.services.matches.scorecard_service import (
        get_match_scorecard,
    )

    return get_match_scorecard(match_id)