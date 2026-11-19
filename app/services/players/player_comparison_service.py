from typing import Optional

from app.services.players.player_service import get_player_batting_stats
from app.services.players.bowling_service import get_player_bowling_stats


def _get_player_stats(player_name: str, season: Optional[str] = None):
    batting = (
        get_player_batting_stats(player_name, season=season)
        if season
        else get_player_batting_stats(player_name)
    )

    if not batting:
        scope = f" in IPL {season}" if season else ""
        raise ValueError(f"No player found matching '{player_name}'{scope}.")

    if len(batting) > 1:
        matches = ", ".join(p["player_name"] for p in batting)
        raise ValueError(
            f"Ambiguous player name '{player_name}'. "
            f"Please use a specific name. Matches: {matches}"
        )

    player_id = batting[0]["player_id"]

    bowling = (
        get_player_bowling_stats(player_name, season=season)
        if season
        else get_player_bowling_stats(player_name)
    )
    bowling = [
        player for player in bowling
        if player["player_id"] == player_id
    ]

    return {
        "batting": batting[0],
        "bowling": bowling[0] if bowling else None,
    }


def compare_players(player_one: str, player_two: str, season: Optional[str] = None):
    if not player_one or not player_two:
        raise ValueError("Both player names are required.")

    if player_one.strip().lower() == player_two.strip().lower():
        raise ValueError("Please provide two different players.")

    if season:
        return {
            "player_one": _get_player_stats(player_one, season=season),
            "player_two": _get_player_stats(player_two, season=season),
        }

    return {
        "player_one": _get_player_stats(player_one),
        "player_two": _get_player_stats(player_two),
    }
