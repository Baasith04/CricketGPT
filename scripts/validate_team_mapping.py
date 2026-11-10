
import json
from pathlib import Path

DATASET = Path(r"C:\Users\CFRSI 4\Downloads\ipl_json")

TEAM_MAPPING = {
    "Chennai Super Kings": "Chennai Super Kings",
    "Deccan Chargers": "Deccan Chargers",
    "Delhi Daredevils": "Delhi Capitals",
    "Delhi Capitals": "Delhi Capitals",
    "Gujarat Lions": "Gujarat Lions",
    "Gujarat Titans": "Gujarat Titans",
    "Kings XI Punjab": "Punjab Kings",
    "Punjab Kings": "Punjab Kings",
    "Kochi Tuskers Kerala": "Kochi Tuskers Kerala",
    "Kolkata Knight Riders": "Kolkata Knight Riders",
    "Lucknow Super Giants": "Lucknow Super Giants",
    "Mumbai Indians": "Mumbai Indians",
    "Pune Warriors": "Pune Warriors",
    "Rajasthan Royals": "Rajasthan Royals",
    "Rising Pune Supergiant": "Rising Pune Supergiants",
    "Rising Pune Supergiants": "Rising Pune Supergiants",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Royal Challengers Bengaluru": "Royal Challengers Bengaluru",
    "Sunrisers Hyderabad": "Sunrisers Hyderabad",
}


def main():
    discovered_names = set()
    unknown_names = set()

    for file_path in DATASET.glob("*.json"):
        with file_path.open("r", encoding="utf-8") as file:
            match = json.load(file)

        for team_name in match["info"]["teams"]:
            discovered_names.add(team_name)

            if team_name not in TEAM_MAPPING:
                unknown_names.add(team_name)

    print("\n========== TEAM MAPPING REPORT ==========")
    print("Historical team names:", len(discovered_names))
    print("Mapped team names:", len(discovered_names) - len(unknown_names))
    print("Unknown team names:", len(unknown_names))

    for name in sorted(discovered_names):
        print(f"{name} -> {TEAM_MAPPING.get(name, 'UNKNOWN')}")

    if unknown_names:
        print("\nUnmapped names:", sorted(unknown_names))
    else:
        print("\nAll team names successfully mapped.")


if __name__ == "__main__":
    main()
    