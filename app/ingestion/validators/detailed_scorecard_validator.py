
from collections import defaultdict


EXTRA_FIELDS = (
    "wide_runs",
    "no_ball_runs",
    "bye_runs",
    "leg_bye_runs",
    "penalty_runs",
)


def _number(row, field):
    return int(row.get(field) or 0)


def calculate_detailed_scorecards(delivery_rows, wicket_rows, innings_rows):
    """
    Calculate batting, bowling and extras figures from raw deliveries.

    This function does not modify the database.
    """

    batters = defaultdict(lambda: {
        "match_id": None,
        "innings_id": None,
        "player_id": None,
        "player_name": None,
        "runs": 0,
        "balls_faced": 0,
        "fours": 0,
        "sixes": 0,
        "dismissals": 0,
    })

    bowlers = defaultdict(lambda: {
        "match_id": None,
        "innings_id": None,
        "player_id": None,
        "player_name": None,
        "runs_conceded": 0,
        "legal_balls": 0,
        "wickets": 0,
    })

    innings_totals = defaultdict(lambda: {
        "match_id": None,
        "innings_id": None,
        "batter_runs": 0,
        "extras": 0,
        "delivery_runs": 0,
        "wide_runs": 0,
        "no_ball_runs": 0,
        "bye_runs": 0,
        "leg_bye_runs": 0,
        "penalty_runs": 0,
        "delivery_count": 0,
        "legal_balls": 0,
        "wickets": 0,
    })

    # Calculate delivery-level batting, bowling and extras.
    for row in delivery_rows:
        match_id = row["match_id"]
        innings_id = row["innings_id"]

        batter_key = (innings_id, row["batter_id"])
        bowler_key = (innings_id, row["bowler_id"])

        batter = batters[batter_key]
        batter["match_id"] = match_id
        batter["innings_id"] = innings_id
        batter["player_id"] = row["batter_id"]
        batter["player_name"] = row["batter_name"]

        bowler = bowlers[bowler_key]
        bowler["match_id"] = match_id
        bowler["innings_id"] = innings_id
        bowler["player_id"] = row["bowler_id"]
        bowler["player_name"] = row["bowler_name"]

        batter_runs = _number(row, "batter_runs")
        extra_runs = _number(row, "extra_runs")
        total_runs = _number(row, "total_runs")
        wide_runs = _number(row, "wide_runs")
        no_ball_runs = _number(row, "no_ball_runs")
        bye_runs = _number(row, "bye_runs")
        leg_bye_runs = _number(row, "leg_bye_runs")
        penalty_runs = _number(row, "penalty_runs")

        # Batting figures.
        batter["runs"] += batter_runs

        # A wide is not a ball faced. A no-ball is a ball faced.
        if wide_runs == 0:
            batter["balls_faced"] += 1

        if batter_runs == 4:
            batter["fours"] += 1
        elif batter_runs == 6:
            batter["sixes"] += 1

        # Bowling figures.
        # Byes, leg-byes and penalty runs are not charged to the bowler.
        bowler["runs_conceded"] += (
            batter_runs + wide_runs + no_ball_runs
        )

        if row["is_legal_ball"]:
            bowler["legal_balls"] += 1

        # Innings-level reconciliation.
        innings = innings_totals[innings_id]
        innings["match_id"] = match_id
        innings["innings_id"] = innings_id
        innings["batter_runs"] += batter_runs
        innings["extras"] += extra_runs
        innings["delivery_runs"] += total_runs
        innings["wide_runs"] += wide_runs
        innings["no_ball_runs"] += no_ball_runs
        innings["bye_runs"] += bye_runs
        innings["leg_bye_runs"] += leg_bye_runs
        innings["penalty_runs"] += penalty_runs
        innings["delivery_count"] += 1
        if row["is_legal_ball"]:
            innings["legal_balls"] += 1

    
    # Calculate dismissals and bowler-credited wickets efficiently.
    delivery_by_id = {
        row["delivery_id"]: row
        for row in delivery_rows
    }

    for wicket in wicket_rows:
        innings_id = wicket["innings_id"]
        player_id = wicket["player_dismissed_id"]
        dismissal_kind = (wicket["dismissal_kind"] or "").lower()

        # Count wickets except retired hurt.
        if dismissal_kind != "retired hurt":
            innings_totals[innings_id]["wickets"] += 1

        # Count batter dismissals.
        if player_id and dismissal_kind != "retired hurt":
            batter_key = (innings_id, player_id)
            batter = batters[batter_key]
            batter["innings_id"] = innings_id
            batter["player_id"] = player_id
            batter["dismissals"] += 1

    
       # Retired hurt must never count as a bowler wicket.
        if (
            dismissal_kind != "retired hurt"
            and wicket["is_bowler_credit"]
        ):
            matching_delivery = delivery_by_id.get(
                wicket["delivery_id"]
            )

            if matching_delivery:
                bowler_key = (
                    matching_delivery["innings_id"],
                    matching_delivery["bowler_id"],
                )
                bowlers[bowler_key]["wickets"] += 1

    innings_results = []

    for stored in innings_rows:
        innings_id = stored["innings_id"]
        calculated = innings_totals[innings_id]

        stored_runs = _number(stored, "total_runs")
        stored_wickets = _number(stored, "total_wickets")
        stored_legal_balls = _number(stored, "legal_balls_bowled")

        delivery_runs = calculated["delivery_runs"]
        batter_and_extras = (
            calculated["batter_runs"] + calculated["extras"]
        )

        calculated_legal_balls = sum(
            1 for row in delivery_rows
            if row["innings_id"] == innings_id
            and row["is_legal_ball"]
        )

        innings_wickets = sum(
            1 for wicket in wicket_rows
            if wicket["innings_id"] == innings_id
            and (wicket["dismissal_kind"] or "").lower()
                != "retired hurt"
        )

        checks = {
            "delivery_runs_match": delivery_runs == stored_runs,
            "batter_plus_extras_match": (
                batter_and_extras == stored_runs
            ),
            "legal_balls_match": (
                calculated_legal_balls == stored_legal_balls
            ),
            "wickets_match": innings_wickets == stored_wickets,
        }

        innings_results.append({
            "match_id": stored["match_id"],
            "innings_id": innings_id,
            "innings_number": stored["innings_number"],
            "is_super_over": stored["is_super_over"],
            "stored_total_runs": stored_runs,
            "calculated_total_runs": delivery_runs,
            "batter_runs": calculated["batter_runs"],
            "extras": calculated["extras"],
            "stored_wickets": stored_wickets,
            "calculated_wickets": innings_wickets,
            "stored_legal_balls": stored_legal_balls,
            "calculated_legal_balls": calculated_legal_balls,
            "checks": checks,
            "is_valid": all(checks.values()),
        })

    batter_results = []

    for batter in batters.values():
        balls = batter["balls_faced"]
        runs = batter["runs"]

        batter_results.append({
            **batter,
            "strike_rate": (
                round(runs * 100 / balls, 2) if balls else 0.0
            ),
        })

    bowler_results = []

    for bowler in bowlers.values():
        balls = bowler["legal_balls"]
        runs = bowler["runs_conceded"]

        bowler_results.append({
            **bowler,
            "overs": f"{balls // 6}.{balls % 6}",
            "economy": (
                round(runs * 6 / balls, 2) if balls else 0.0
            ),
        })

    return {
        "total_innings": len(innings_results),
        "valid_innings": sum(
            result["is_valid"] for result in innings_results
        ),
        "invalid_innings": sum(
            not result["is_valid"] for result in innings_results
        ),
        "batters_calculated": len(batter_results),
        "bowlers_calculated": len(bowler_results),
        "batters": batter_results,
        "bowlers": bowler_results,
        "innings": innings_results,
        "limitations": [
            "Boundary counts may be inaccurate for non-boundary fours or sixes because the schema does not store the non_boundary flag.",
            "This validator calculates player figures from deliveries; it does not compare them with a separate stored player-scorecard table.",
        ],
    }
