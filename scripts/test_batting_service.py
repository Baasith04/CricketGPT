
from app.services.statistics.batting_service import (
    get_batting_leaderboard,
    get_player_batting_stats,
)


print("\n--- TOP 5 IPL BATTERS ---")

leaderboard = get_batting_leaderboard(limit=5)

for index, player in enumerate(leaderboard, start=1):
    print(
        f"{index}. {player['player_name']} | "
        f"Runs: {player['total_runs']} | "
        f"Average: {player['batting_average']} | "
        f"Strike Rate: {player['strike_rate']}"
    )


print("\n--- VIRAT KOHLI CAREER STATS ---")

kohli = get_player_batting_stats("ba607b88")

if kohli:
    for key, value in kohli.items():
        print(f"{key}: {value}")
else:
    print("Player not found.")
