from pprint import pprint

from app.services.players.player_service import (
    get_player_batting_stats,
)
from app.services.players.bowling_service import (
    get_player_bowling_stats,
)
from app.services.players.player_comparison_service import (
    compare_players,
)


def main():
    print("\n========== BATTING STATISTICS ==========")

    batting = get_player_batting_stats("Ganguly")
    pprint(batting)

    print("\n========== BOWLING STATISTICS ==========")

    bowling = get_player_bowling_stats("Khan")
    pprint(bowling)

    print("\n========== PLAYER COMPARISON ==========")

    comparison = compare_players("SC Ganguly", "V Kohli")
    pprint(comparison)


if __name__ == "__main__":
    main()