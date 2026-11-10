
from app.database.connection import get_db_connection

from app.services.statistics.leaderboard_service import (
    get_batting_leaderboard,
    get_bowling_leaderboard,
    get_best_bowling_figures,
)


def get_available_seasons():
    """Return all IPL seasons available in the database."""

    query = """
        SELECT season
        FROM matches
        WHERE season IS NOT NULL
        GROUP BY season
        ORDER BY MIN(match_date)
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [row[0] for row in cur.fetchall()]



def get_orange_cap_winner(season: str):
    """Return all players tied for the highest runs."""

    rows = get_batting_leaderboard(
        category="runs",
        season=season,
        limit=100,
    )

    if not rows:
        return []

    highest_runs = rows[0]["total_runs"]

    return [
        row for row in rows
        if row["total_runs"] == highest_runs
    ]


def get_purple_cap_winner(season: str):
    """Return all players tied for the highest wickets."""

    rows = get_bowling_leaderboard(
        category="wickets",
        season=season,
        limit=100,
    )

    if not rows:
        return []

    highest_wickets = rows[0]["wickets"]

    return [
        row for row in rows
        if row["wickets"] == highest_wickets
    ]


def get_season_best_bowling(season: str):
    """Return all players tied for the best bowling figures."""

    rows = get_best_bowling_figures(
        season=season,
        limit=100,
    )

    if not rows:
        return []

    best_wickets = rows[0]["wickets"]
    best_runs = rows[0]["runs_conceded"]

    return [
        row for row in rows
        if (
            row["wickets"] == best_wickets
            and row["runs_conceded"] == best_runs
        )
    ]


def get_season_best_strike_rate(
    season: str,
    min_balls: int = 100,
):
    """Return all qualified players tied for the highest strike rate."""

    rows = get_batting_leaderboard(
        category="strike_rate",
        season=season,
        limit=100,
        min_balls=min_balls,
    )

    if not rows:
        return []

    best_rate = rows[0]["strike_rate"]

    return [
        row for row in rows
        if row["strike_rate"] == best_rate
    ]


def get_all_orange_cap_winners():
    """Return Orange Cap winners across all available IPL seasons."""
    return {
        season: get_orange_cap_winner(season)
        for season in get_available_seasons()
    }


def get_all_purple_cap_winners():
    """Return Purple Cap winners across all available IPL seasons."""
    return {
        season: get_purple_cap_winner(season)
        for season in get_available_seasons()
    }


def get_all_season_best_bowling():
    """Return best bowling figures across all available IPL seasons."""
    return {
        season: get_season_best_bowling(season)
        for season in get_available_seasons()
    }


def get_all_season_best_strike_rates(min_balls: int = 100):
    """Return highest strike rates across all available IPL seasons."""
    return {
        season: get_season_best_strike_rate(season, min_balls=min_balls)
        for season in get_available_seasons()
    }


