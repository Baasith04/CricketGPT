import re
from typing import Optional

from app.database.connection import get_db_connection

# Common full names and nicknames mapped to Cricsheet canonical names.
# Note: Only player identity mappings here; all statistics come from PostgreSQL.
PLAYER_NAME_ALIASES = {
    "virat kohli": "V Kohli",
    "kohli": "V Kohli",
    "rohit sharma": "RG Sharma",
    "rohit": "RG Sharma",
    "ms dhoni": "MS Dhoni",
    "m s dhoni": "MS Dhoni",
    "mahendra singh dhoni": "MS Dhoni",
    "dhoni": "MS Dhoni",
    "jasprit bumrah": "JJ Bumrah",
    "bumrah": "JJ Bumrah",
    "suryakumar yadav": "SA Yadav",
    "surya": "SA Yadav",
    "hardik pandya": "HH Pandya",
    "krunal pandya": "KH Pandya",
    "ravindra jadeja": "RA Jadeja",
    "jadeja": "RA Jadeja",
    "kl rahul": "KL Rahul",
    "k l rahul": "KL Rahul",
    "lokesh rahul": "KL Rahul",
    "ab de villiers": "AB de Villiers",
    "abd": "AB de Villiers",
    "chris gayle": "CH Gayle",
    "gayle": "CH Gayle",
    "david warner": "DA Warner",
    "warner": "DA Warner",
    "suresh raina": "SK Raina",
    "raina": "SK Raina",
    "shikhar dhawan": "S Dhawan",
    "dhawan": "S Dhawan",
    "bhuvneshwar kumar": "B Kumar",
    "sunil narine": "SP Narine",
    "narine": "SP Narine",
    "andre russell": "AD Russell",
    "russell": "AD Russell",
    "yuzvendra chahal": "YS Chahal",
    "chahal": "YS Chahal",
    "rashid khan": "Rashid Khan",
    "shubman gill": "Shubman Gill",
    "gill": "Shubman Gill",
    "rishabh pant": "RR Pant",
    "pant": "RR Pant",
    "shreyas iyer": "SS Iyer",
    "dinesh karthik": "KD Karthik",
    "r ashwin": "R Ashwin",
    "ravichandran ashwin": "R Ashwin",
    "ashwin": "R Ashwin",
    "ajinkya rahane": "AM Rahane",
    "sanju samson": "SV Samson",
    "jos buttler": "JC Buttler",
    "buttler": "JC Buttler",
    "glenn maxwell": "GJ Maxwell",
    "maxwell": "GJ Maxwell",
    "faf du plessis": "F du Plessis",
    "kieron pollard": "KA Pollard",
    "pollard": "KA Pollard",
    "lasith malinga": "SL Malinga",
    "malinga": "SL Malinga",
    "gautam gambhir": "G Gambhir",
    "yuvraj singh": "Yuvraj Singh",
    "sachin tendulkar": "SR Tendulkar",
    "tendulkar": "SR Tendulkar",
}


def resolve_player_sql_filter(player_name: str):
    """
    Build a parameterized SQL predicate and parameter tuple for matching `players p`.

    Supports:
    - Common full-name aliases (e.g. 'Virat Kohli' -> 'V Kohli')
    - Substring canonical_name match (ILIKE)
    - Dynamic initial + surname fallback (e.g. 'Trent Boult' -> '^T[A-Z]{0,2}\\s+Boult$')
    """
    cleaned = re.sub(r"\s+", " ", player_name.strip())
    lowered = cleaned.lower()

    if lowered in PLAYER_NAME_ALIASES:
        canonical = PLAYER_NAME_ALIASES[lowered]
        return "p.canonical_name ILIKE %s", (canonical,)

    tokens = cleaned.split(" ")
    if len(tokens) >= 2:
        first_initial = re.escape(tokens[0][0])
        surname = re.escape(tokens[-1])
        initial_pattern = rf"^{first_initial}[A-Za-z]{{0,2}}\s+{surname}$"
        return (
            "(p.canonical_name ILIKE %s OR p.canonical_name ~* %s)",
            (f"%{cleaned}%", initial_pattern),
        )

    return "p.canonical_name ILIKE %s", (f"%{cleaned}%",)


def _rows_to_dicts(cursor, rows):
    """Convert database rows into dictionaries."""
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_player_batting_stats(player_name: str, season: Optional[str] = None):
    """
    Return batting statistics for players matching `player_name`,
    optionally filtered by `season` (e.g. '2024', '2007/08').
    Super Over innings are excluded.
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
        innings_scores AS (
            SELECT
                d.batter_id AS player_id,
                d.match_id,
                d.innings_id,
                SUM(d.batter_runs) AS innings_runs
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            WHERE d.batter_id IN (SELECT player_id FROM matched_players)
              AND i.is_super_over = FALSE
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY d.batter_id, d.match_id, d.innings_id
        ),
        batting AS (
            SELECT
                d.batter_id AS player_id,
                COUNT(DISTINCT d.match_id) AS batting_matches,
                COUNT(DISTINCT d.innings_id) AS innings_batted,
                SUM(d.batter_runs) AS total_runs,
                COUNT(*) FILTER (WHERE d.wide_runs = 0) AS balls_faced,
                COUNT(*) FILTER (WHERE d.batter_runs = 4) AS fours,
                COUNT(*) FILTER (WHERE d.batter_runs = 6) AS sixes
            FROM deliveries d
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = d.match_id
            WHERE d.batter_id IN (SELECT player_id FROM matched_players)
              AND i.is_super_over = FALSE
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY d.batter_id
        ),
        milestones AS (
            SELECT
                player_id,
                MAX(innings_runs) AS highest_score,
                COUNT(*) FILTER (WHERE innings_runs >= 50 AND innings_runs < 100) AS fifties,
                COUNT(*) FILTER (WHERE innings_runs >= 100) AS hundreds
            FROM innings_scores
            GROUP BY player_id
        ),
        dismissals AS (
            SELECT
                dw.player_dismissed_id AS player_id,
                COUNT(*) FILTER (
                    WHERE LOWER(dw.dismissal_kind) <> 'retired hurt'
                ) AS dismissals
            FROM delivery_wickets dw
            JOIN deliveries d ON d.delivery_id = dw.delivery_id
            JOIN innings i ON i.innings_id = d.innings_id
            JOIN matches m ON m.match_id = dw.match_id
            WHERE dw.player_dismissed_id IN (SELECT player_id FROM matched_players)
              AND i.is_super_over = FALSE
              AND (%s::varchar IS NULL OR m.season = %s::varchar)
            GROUP BY dw.player_dismissed_id
        ),
        appearances AS (
            SELECT participants.player_id, COUNT(DISTINCT participants.match_id) AS matches_played
            FROM (
                SELECT d.batter_id AS player_id, d.match_id
                FROM deliveries d
                JOIN innings i ON i.innings_id = d.innings_id
                JOIN matches m ON m.match_id = d.match_id
                WHERE i.is_super_over = FALSE
                  AND (%s::varchar IS NULL OR m.season = %s::varchar)
                UNION
                SELECT d.bowler_id AS player_id, d.match_id
                FROM deliveries d
                JOIN innings i ON i.innings_id = d.innings_id
                JOIN matches m ON m.match_id = d.match_id
                WHERE i.is_super_over = FALSE
                  AND (%s::varchar IS NULL OR m.season = %s::varchar)
                UNION
                SELECT d.non_striker_id AS player_id, d.match_id
                FROM deliveries d
                JOIN innings i ON i.innings_id = d.innings_id
                JOIN matches m ON m.match_id = d.match_id
                WHERE i.is_super_over = FALSE
                  AND (%s::varchar IS NULL OR m.season = %s::varchar)
                UNION
                SELECT dw.player_dismissed_id AS player_id, dw.match_id
                FROM delivery_wickets dw
                JOIN matches m ON m.match_id = dw.match_id
                WHERE (%s::varchar IS NULL OR m.season = %s::varchar)
            ) participants
            WHERE participants.player_id IN (SELECT player_id FROM matched_players)
            GROUP BY participants.player_id
        )
        SELECT
            mp.player_id,
            mp.canonical_name AS player_name,
            COALESCE(a.matches_played, 0) AS matches_played,
            COALESCE(b.innings_batted, 0) AS innings_batted,
            COALESCE(b.total_runs, 0) AS total_runs,
            COALESCE(ms.highest_score, 0) AS highest_score,
            COALESCE(b.balls_faced, 0) AS balls_faced,
            COALESCE(b.fours, 0) AS fours,
            COALESCE(b.sixes, 0) AS sixes,
            COALESCE(ms.fifties, 0) AS fifties,
            COALESCE(ms.hundreds, 0) AS hundreds,
            COALESCE(ds.dismissals, 0) AS dismissals,
            GREATEST(COALESCE(b.innings_batted, 0) - COALESCE(ds.dismissals, 0), 0) AS not_outs,
            CASE
                WHEN COALESCE(ds.dismissals, 0) = 0 THEN NULL
                ELSE ROUND(b.total_runs::NUMERIC / ds.dismissals, 2)
            END AS batting_average,
            CASE
                WHEN COALESCE(b.balls_faced, 0) = 0 THEN 0
                ELSE ROUND(b.total_runs::NUMERIC * 100 / b.balls_faced, 2)
            END AS strike_rate
        FROM matched_players mp
        LEFT JOIN batting b ON b.player_id = mp.player_id
        LEFT JOIN milestones ms ON ms.player_id = mp.player_id
        LEFT JOIN dismissals ds ON ds.player_id = mp.player_id
        LEFT JOIN appearances a ON a.player_id = mp.player_id
        WHERE (%s::varchar IS NULL OR COALESCE(a.matches_played, 0) > 0)
        ORDER BY total_runs DESC, matches_played DESC, mp.canonical_name;
    """

    params = (
        *player_params,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
        normalized_season, normalized_season,
        normalized_season,
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return _rows_to_dicts(cur, rows)
