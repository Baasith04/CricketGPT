
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


def get_all_season_winners():
    """
    Get the winner of the latest recorded match in each IPL season.

    The current Cricsheet import has NULL stage and match_number values,
    so the latest match date is used to identify the season final.
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
        LEFT JOIN teams t
            ON t.team_id = fm.winner_id
        WHERE fm.rn = 1
        ORDER BY fm.match_date;
    """

    return _fetch_all(query)


def get_season_winner(season: str):
    """Get the recorded winner of a specific IPL season."""

    if not isinstance(season, str) or not season.strip():
        raise ValueError("Season must be a non-empty string.")

    query = """
        WITH final_match AS (
            SELECT
                m.match_id,
                m.season,
                m.match_date,
                m.winner_id
            FROM matches m
            WHERE m.season = %s
            ORDER BY m.match_date DESC, m.match_id DESC
            LIMIT 1
        )
        SELECT
            fm.season,
            fm.match_id,
            fm.match_date,
            t.team_id,
            t.canonical_name AS winner
        FROM final_match fm
        LEFT JOIN teams t
            ON t.team_id = fm.winner_id;
    """

    rows = _fetch_all(query, (season.strip(),))
    return rows[0] if rows else None


def get_all_team_trophy_counts():
    """Count recorded IPL season championships for every team."""

    query = """
        WITH season_winners AS (
            SELECT DISTINCT ON (m.season)
                m.season,
                m.winner_id
            FROM matches m
            ORDER BY
                m.season,
                m.match_date DESC,
                m.match_id DESC
        )
        SELECT
            t.team_id,
            t.canonical_name AS team_name,
            t.short_code,
            COUNT(sw.season) AS trophies
        FROM teams t
        LEFT JOIN season_winners sw
            ON sw.winner_id = t.team_id
        GROUP BY
            t.team_id,
            t.canonical_name,
            t.short_code
        ORDER BY trophies DESC, t.canonical_name;
    """

    return _fetch_all(query)


def get_team_trophy_count(team_name: str):
    """Get the recorded IPL trophy count for a specific team."""

    if not isinstance(team_name, str) or not team_name.strip():
        raise ValueError("Team name cannot be empty.")

    query = """
        WITH season_winners AS (
            SELECT DISTINCT ON (m.season)
                m.season,
                m.winner_id
            FROM matches m
            ORDER BY
                m.season,
                m.match_date DESC,
                m.match_id DESC
        )
        SELECT
            t.team_id,
            t.canonical_name AS team_name,
            COUNT(sw.season) AS trophies
        FROM teams t
        LEFT JOIN season_winners sw
            ON sw.winner_id = t.team_id
        WHERE
            t.canonical_name ILIKE %s
            OR t.short_code ILIKE %s
            OR EXISTS (
                SELECT 1
                FROM team_aliases ta
                WHERE ta.team_id = t.team_id
                  AND ta.alias_name ILIKE %s
            )
        GROUP BY t.team_id, t.canonical_name
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
