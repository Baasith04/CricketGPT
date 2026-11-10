from app.database.connection import get_db_connection


def _find_team(team_name: str):
    query = """
        SELECT team_id, canonical_name
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

    search = f"%{team_name.strip()}%"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (search, search, search))
            rows = cur.fetchall()

    if not rows:
        raise ValueError(f"Team '{team_name}' was not found.")

    if len(rows) > 1:
        names = ", ".join(row[1] for row in rows)
        raise ValueError(
            f"Ambiguous team '{team_name}'. Matches: {names}"
        )

    return {"team_id": rows[0][0], "team_name": rows[0][1]}


def get_head_to_head(team_one: str, team_two: str):
    if not team_one or not team_two:
        raise ValueError("Both team names are required.")

    first = _find_team(team_one)
    second = _find_team(team_two)

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
            ) AS ties,
            COUNT(*) FILTER (
                WHERE m.result_type = 'no result'
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