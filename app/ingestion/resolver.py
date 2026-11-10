
from app.database.connection import get_db_connection


def resolve_team_id(team_name: str) -> int:
    """
    Resolve a Cricsheet team name to its canonical database team ID.
    Supports both canonical names and historical aliases.
    """
    query = """
        SELECT team_id
        FROM teams
        WHERE canonical_name = %s

        UNION

        SELECT team_id
        FROM team_aliases
        WHERE alias_name = %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (team_name, team_name))
            results = cur.fetchall()

    if len(results) != 1:
        raise ValueError(
            f"Team resolution failed for '{team_name}'. "
            f"Expected one result, found {len(results)}."
        )

    return results[0][0]


def resolve_player_id(
    registry_id: str,
    match_display_name: str
) -> str:
    """
    Verify that a Cricsheet player registry ID exists in the database.
    """
    query = """
        SELECT player_id
        FROM players
        WHERE player_id = %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (registry_id,))
            result = cur.fetchone()

    if result is None:
        raise ValueError(
            f"Player not found: {match_display_name} "
            f"(registry ID: {registry_id})"
        )

    return result[0]
