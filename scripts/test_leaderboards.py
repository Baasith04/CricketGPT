
from pprint import pprint

from app.services.statistics.leaderboard_service import (
    get_batting_leaderboard,
    get_bowling_leaderboard,
    get_best_bowling_figures,
)

tests = [
    ("Orange Cap", lambda: get_batting_leaderboard(category="runs")),
    ("Highest Score", lambda: get_batting_leaderboard(category="highest_score")),
    ("Most Sixes", lambda: get_batting_leaderboard(category="sixes")),
    ("Most Fours", lambda: get_batting_leaderboard(category="fours")),
    ("Purple Cap", lambda: get_bowling_leaderboard(category="wickets")),
    ("Best Economy", lambda: get_bowling_leaderboard(category="economy")),
    ("Best Bowling Figures", lambda: get_best_bowling_figures()),
]

for title, function in tests:
    print(f"\n{'=' * 15} {title} {'=' * 15}")
    try:
        pprint(function())
    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}")
