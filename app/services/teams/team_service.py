from app.database.connection import get_db_connection


def _fetch_all(query, params=()):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [col.name for col in cur.description]
            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]


def get_team_profile(team_name: str):
    if not team_name or not team_name.strip():
        raise ValueError("Team name cannot be empty.")

    query = """
        SELECT
            t.team_id,
            t.canonical_name AS team_name,
            t.short_code,
            t.is_active,
            COUNT(DISTINCT mt.match_id) AS matches_played,
            COUNT(DISTINCT m.match_id) FILTER (
                WHERE m.winner_id = t.team_id
            ) AS wins,
            COUNT(DISTINCT m.match_id) FILTER (
                WHERE m.result_type = 'tie'
            ) AS ties,
            COUNT(DISTINCT m.match_id) FILTER (
                WHERE m.result_type = 'no result'
            ) AS no_results,
            COUNT(DISTINCT m.match_id) FILTER (
                WHERE m.winner_id IS NOT NULL
                  AND m.winner_id <> t.team_id
            ) AS losses
        FROM teams t
        LEFT JOIN match_teams mt
            ON mt.team_id = t.team_id
        LEFT JOIN matches m
            ON m.match_id = mt.match_id
        WHERE
            t.canonical_name ILIKE %s
            OR t.short_code ILIKE %s
            OR EXISTS (
                SELECT 1
                FROM team_aliases ta
                WHERE ta.team_id = t.team_id
                  AND ta.alias_name ILIKE %s
            )
        GROUP BY
            t.team_id,
            t.canonical_name,
            t.short_code,
            t.is_active
        ORDER BY t.canonical_name;
    """

    search = f"%{team_name.strip()}%"
    rows = _fetch_all(query, (search, search, search))

    if not rows:
        return None

    if len(rows) > 1:
        raise ValueError(
            f"Ambiguous team name '{team_name}'. "
            "Please provide a more specific name."
        )

    return rows[0]


def get_all_teams(active_only: bool = False):
    query = """
        SELECT
            team_id,
            canonical_name AS team_name,
            short_code,
            is_active
        FROM teams
    """

    if active_only:
        query += " WHERE is_active = TRUE"

    query += " ORDER BY canonical_name"

    return _fetch_all(query)