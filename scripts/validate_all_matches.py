
from pathlib import Path
from collections import Counter

from app.ingestion.parser import parse_match

DATASET = Path(r"C:\Users\CFRSI 4\Downloads\ipl_json")

VALID_DISMISSALS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "run out",
    "hit wicket",
    "retired hurt",
    "retired out",
    "obstructing the field",
    "hit the ball twice",
    "handled the ball",
    "timed out",
}


def validate_match(match):
    errors = []

    # 1. Exactly two distinct teams.
    teams = match["teams"]

    if len(teams) != 2 or len(set(teams)) != 2:
        errors.append("Invalid participating teams")

    # 2. Every player has a registry ID.
    player_ids = [
        player["player_id"]
        for player in match["players"]
    ]

    if any(not player_id for player_id in player_ids):
        errors.append("Player missing registry ID")

    if len(player_ids) != len(set(player_ids)):
        errors.append("Duplicate player ID in match squad")

    # 3. Every delivery has consistent run totals.
    for innings in match["innings"]:
        for delivery in innings["deliveries"]:

            if delivery["total_runs"] != (
                delivery["batter_runs"] + delivery["extra_runs"]
            ):
                errors.append("Delivery run total mismatch")

            extras_sum = sum(
                delivery[key]
                for key in (
                    "wides",
                    "noballs",
                    "legbyes",
                    "byes",
                    "penalty",
                )
            )

            if extras_sum != delivery["extra_runs"]:
                errors.append("Delivery extras total mismatch")

            # 4. Check dismissal records.
            for wicket in delivery["wickets"]:

                if wicket["dismissal_kind"] not in VALID_DISMISSALS:
                    errors.append(
                        f"Unknown dismissal type: {wicket['dismissal_kind']}"
                    )

                if not wicket["player_out"]:
                    errors.append("Wicket missing dismissed player")

    # 5. Check innings and delivery presence.
    if not match["innings"]:
        errors.append("Match contains no innings")

    for innings in match["innings"]:
        if not innings["deliveries"]:
            errors.append(
                f"Innings {innings['innings_number']} has no deliveries"
            )

    return errors


def main():
    files = list(DATASET.glob("*.json"))

    total_matches = 0
    passed_matches = 0
    failed_matches = []
    dismissal_counts = Counter()

    for file_path in files:
        total_matches += 1

        try:
            match = parse_match(file_path)
            errors = validate_match(match)

            if errors:
                failed_matches.append((file_path.name, errors))
            else:
                passed_matches += 1

            for innings in match["innings"]:
                for delivery in innings["deliveries"]:
                    for wicket in delivery["wickets"]:
                        dismissal_counts[
                            wicket["dismissal_kind"]
                        ] += 1

        except Exception as error:
            failed_matches.append((file_path.name, [str(error)]))

    print("\n========== DATA VALIDATION REPORT ==========")
    print("Total matches:", total_matches)
    print("Passed:", passed_matches)
    print("Failed:", len(failed_matches))

    if failed_matches:
        print("\n========== VALIDATION ERRORS ==========")

        for filename, errors in failed_matches[:30]:
            print("\nFile:", filename)

            for error in errors:
                print(" -", error)

    print("\n========== DISMISSAL TYPES FOUND ==========")

    for dismissal, count in sorted(dismissal_counts.items()):
        print(f"{dismissal}: {count}")

    print("\nValidation completed.")


if __name__ == "__main__":
    main()
