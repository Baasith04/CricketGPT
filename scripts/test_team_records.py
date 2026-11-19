
from pprint import pprint

from app.services.statistics.team_records_service import (
    get_all_season_winners,
    get_all_team_trophy_counts,
    get_season_winner,
    get_team_trophy_count,
)


print("\n===== IPL SEASON WINNERS =====")
pprint(get_all_season_winners())

print("\n===== TEAM TROPHY COUNTS =====")
pprint(get_all_team_trophy_counts())

print("\n===== CSK TROPHY COUNT =====")
pprint(get_team_trophy_count("CSK"))

print("\n===== IPL 2026 WINNER =====")
pprint(get_season_winner("2026"))
