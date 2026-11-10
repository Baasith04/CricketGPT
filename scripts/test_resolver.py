
from app.ingestion.resolver import resolve_team_id, resolve_player_id


def main():
    print("========== RESOLVER TEST ==========")

    team_id = resolve_team_id("Royal Challengers Bangalore")
    print("Historical team resolved. Team ID:", team_id)

    player_id = resolve_player_id(
        "12314277",
        "Arshad Khan"
    )
    print("Player resolved. Player ID:", player_id)

    print("\nResolver test completed.")


if __name__ == "__main__":
    main()
