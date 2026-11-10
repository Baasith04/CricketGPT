from app.services.players.player_service import get_player_batting_stats
from app.services.players.bowling_service import get_player_bowling_stats


def _get_player_stats(player_name: str):
    batting = get_player_batting_stats(player_name)

    if not batting:
        raise ValueError(f"No player found matching '{player_name}'.")

    if len(batting) > 1:
        matches = ", ".join(p["player_name"] for p in batting)
        raise ValueError(
            f"Ambiguous player name '{player_name}'. "
            f"Please use a specific name. Matches: {matches}"
        )

    player_id = batting[0]["player_id"]

    bowling = get_player_bowling_stats(player_name)
    bowling = [
        player for player in bowling
        if player["player_id"] == player_id
    ]

    return {
        "batting": batting[0],
        "bowling": bowling[0] if bowling else None,
    }


def compare_players(player_one: str, player_two: str):
    if not player_one or not player_two:
        raise ValueError("Both player names are required.")

    if player_one.strip().lower() == player_two.strip().lower():
        raise ValueError("Please provide two different players.")

    return {
        "player_one": _get_player_stats(player_one),
        "player_two": _get_player_stats(player_two),
    }