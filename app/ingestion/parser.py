
import json
from pathlib import Path


EXTRA_TYPES = (
    "wides",
    "noballs",
    "legbyes",
    "byes",
    "penalty",
)


def parse_match(file_path: str | Path) -> dict:
    """
    Read one Cricsheet JSON file and extract structured match data.

    This function only parses data. It does not connect to the database.
    """
    file_path = Path(file_path)

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    info = data["info"]

    # Validate participating teams.
    teams = info["teams"]

    if len(teams) != 2 or len(set(teams)) != 2:
        raise ValueError("A cricket match must contain exactly two distinct teams.")

    # Map match display names to Cricsheet registry IDs.
    registry = info.get("registry", {}).get("people", {})
    players = []

    for team, squad in info.get("players", {}).items():
        for display_name in squad:
            registry_id = registry.get(display_name)

            if not registry_id:
                raise ValueError(
                    f"Missing registry ID for player: {display_name}"
                )

            players.append({
                "team_name": team,
                "player_id": registry_id,
                "match_display_name": display_name,
            })

    # Extract innings and deliveries.
    innings_list = []

    for innings_number, innings in enumerate(data["innings"], start=1):
        parsed_deliveries = []

        for over in innings["overs"]:
            over_number = over["over"]

            for sequence, delivery in enumerate(over["deliveries"], start=1):
                extras = delivery.get("extras", {})
                runs = delivery["runs"]

                parsed_extras = {
                    extra_type: extras.get(extra_type, 0)
                    for extra_type in EXTRA_TYPES
                }

                wickets = []

                for wicket in delivery.get("wickets", []):
                    wickets.append({
                        "dismissal_kind": wicket["kind"],
                        "player_out": wicket["player_out"],
                        "fielders": [
                            fielder.get("name")
                            for fielder in wicket.get("fielders", [])
                        ],
                    })

                parsed_deliveries.append({
                    "over_number": over_number,
                    "delivery_sequence": sequence,
                    "actual_delivery": delivery.get("actual_delivery"),
                    "batter": delivery["batter"],
                    "bowler": delivery["bowler"],
                    "non_striker": delivery["non_striker"],
                    "batter_runs": runs["batter"],
                    "extra_runs": runs["extras"],
                    "total_runs": runs["total"],
                    **parsed_extras,
                    "wickets": wickets,
                    "review": delivery.get("review"),
                })

        innings_list.append({
            "innings_number": innings_number,
            "batting_team": innings["team"],
            "target": innings.get("target"),
            "is_super_over": innings.get("super_over", False),
            "deliveries": parsed_deliveries,
        })

    # Extract match metadata.
    outcome = info.get("outcome", {})
    event = info.get("event") if isinstance(info.get("event"), dict) else {}
    stage_raw = event.get("stage")
    stage = (
        str(stage_raw).strip()
        if isinstance(stage_raw, str) and stage_raw.strip()
        else None
    )
    raw_match_num = event.get("match_number")
    match_number = (
        raw_match_num
        if isinstance(raw_match_num, int) and not isinstance(raw_match_num, bool) and raw_match_num > 0
        else None
    )
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    raw_rev = meta.get("revision", 1)
    cricsheet_revision = (
        raw_rev
        if isinstance(raw_rev, int) and not isinstance(raw_rev, bool) and raw_rev >= 1
        else 1
    )
    raw_created = meta.get("created")
    cricsheet_created_date = (
        raw_created.strip()
        if isinstance(raw_created, str) and raw_created.strip()
        else None
    )

    return {
        "match_id": int(file_path.stem),
        "season": str(info["season"]),
        "match_number": match_number,
        "stage": stage,
        "dates": info["dates"],
        "venue": info.get("venue"),
        "city": info.get("city"),
        "teams": teams,
        "toss": info.get("toss", {}),
        "winner": outcome.get("winner"),
        "result_by": outcome.get("by", {}),
        "result_method": outcome.get("method"),
        "cricsheet_revision": cricsheet_revision,
        "cricsheet_created_date": cricsheet_created_date,
        "player_of_match": info.get("player_of_match", []),
        "players": players,
        "innings": innings_list,
    }
