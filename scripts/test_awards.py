
from pprint import pprint

from app.services.statistics.awards_service import (
    get_all_orange_cap_winners,
    get_all_purple_cap_winners,
    get_all_season_best_bowling,
    get_all_season_best_strike_rates,
)

print("\n===== ORANGE CAP LEADERS =====")
pprint(get_all_orange_cap_winners())

print("\n===== PURPLE CAP LEADERS =====")
pprint(get_all_purple_cap_winners())

print("\n===== BEST BOWLING FIGURES =====")
pprint(get_all_season_best_bowling())

print("\n===== BEST STRIKE RATES (MINIMUM 100 BALLS) =====")
pprint(get_all_season_best_strike_rates(min_balls=100))
