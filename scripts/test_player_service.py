from pprint import pprint

from app.services.players.player_service import (
    get_player_batting_stats,
)

result = get_player_batting_stats("Ganguly")

print("========== PLAYER BATTING STATISTICS ==========")
print(result)