from pprint import pprint

from app.services.matches.match_service import get_match_result

result = get_match_result(335982)

print("========== MATCH RESULT ==========")
pprint(result)