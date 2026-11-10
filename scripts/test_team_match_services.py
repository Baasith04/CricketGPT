from pprint import pprint

from app.services.teams.team_service import (
    get_team_profile,
    get_all_teams,
)
from app.services.teams.head_to_head_service import (
    get_head_to_head,
)
from app.services.teams.team_statistics_service import (
    get_team_statistics,
)
from app.services.matches.scorecard_service import (
    get_match_scorecard,
)
from app.services.matches.match_list_service import (
    get_matches,
    get_match_by_id,
)


def main():
    match_id = 335982

    print("\n========== TEAM PROFILE ==========")
    pprint(get_team_profile("KKR"))

    print("\n========== ALL TEAMS ==========")
    teams = get_all_teams()
    print("Total teams:", len(teams))
    pprint(teams[:5])

    print("\n========== HEAD TO HEAD ==========")
    pprint(get_head_to_head("KKR", "RCB"))

    print("\n========== TEAM STATISTICS ==========")
    pprint(get_team_statistics("KKR"))

    print("\n========== MATCH LIST ==========")
    pprint(get_matches(
        season="2007/08",
        limit=10,
    ))

    print("\n========== MATCH SEARCH BY TEAM ==========")
    pprint(get_matches(
        team_name="KKR",
        limit=10,
    ))

    print("\n========== MATCH SCORECARD ==========")
    pprint(get_match_scorecard(match_id))

    print("\n========== SCORECARD VIA MATCH SERVICE ==========")
    pprint(get_match_by_id(match_id))


if __name__ == "__main__":
    main()