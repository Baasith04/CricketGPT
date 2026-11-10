
from app.ingestion.parser import parse_match


MATCH_FILE = r"C:\Users\CFRSI 4\Downloads\ipl_json\335982.json"


def main():
    match = parse_match(MATCH_FILE)

    print("\n========== PARSER TEST ==========")
    print("Match ID:", match["match_id"])
    print("Season:", match["season"])
    print("Teams:", match["teams"])
    print("Winner:", match["winner"])
    print("Players:", len(match["players"]))
    print("Innings:", len(match["innings"]))

    total_deliveries = sum(
        len(innings["deliveries"])
        for innings in match["innings"]
    )

    total_wickets = sum(
        len(delivery["wickets"])
        for innings in match["innings"]
        for delivery in innings["deliveries"]
    )

    print("Deliveries:", total_deliveries)
    print("Wickets:", total_wickets)

    print("\nParser test completed.")


if __name__ == "__main__":
    main()
