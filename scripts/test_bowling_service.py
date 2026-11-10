import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.statistics.bowling_service import (
    get_bowling_leaderboard,
    get_player_bowling_stats,
)

print("\n--- TOP 10 IPL BOWLERS ---")

bowlers = get_bowling_leaderboard(limit=10)

for index, bowler in enumerate(bowlers, start=1):
    print(
        f"{index:2d}. {bowler['player_name']:<18} | "
        f"Wkts: {bowler['wickets']:<3} | "
        f"Econ: {bowler['economy']:<5} | "
        f"Avg: {bowler['bowling_average']:<5} | "
        f"Maidens: {bowler['maidens']:<2} | "
        f"Best: {bowler['best_bowling']}"
    )

print("\n--- LASITH MALINGA CAREER STATS (a12e1d51) ---")
malinga = get_player_bowling_stats("a12e1d51")
if malinga:
    for key, value in malinga.items():
        print(f"  {key}: {value}")
else:
    print("Player not found. Check the player ID.")

print("\n--- BHUVNESHWAR KUMAR CAREER STATS (2e81a32d) ---")
bhuvi = get_player_bowling_stats("2e81a32d")
if bhuvi:
    for key, value in bhuvi.items():
        print(f"  {key}: {value}")
else:
    print("Player not found. Check the player ID.")

print("\n--- YS CHAHAL CAREER STATS (57ee1fde) ---")
chahal = get_player_bowling_stats("57ee1fde")
if chahal:
    for key, value in chahal.items():
        print(f"  {key}: {value}")
else:
    print("Player not found. Check the player ID.")
