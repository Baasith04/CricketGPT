
def validate_innings(stored, calculated):
    fields = (
        "total_runs",
        "total_wickets",
        "legal_balls_bowled",
    )

    mismatches = []

    for field in fields:
        expected = stored[field]
        actual = calculated[field]

        if expected != actual:
            mismatches.append({
                "field": field,
                "stored": expected,
                "calculated": actual,
            })

    return {
        "match_id": stored["match_id"],
        "innings_number": stored["innings_number"],
        "is_super_over": stored["is_super_over"],
        "delivery_count": calculated["delivery_count"],
        "is_valid": not mismatches,
        "mismatches": mismatches,
    }


def validate_all_innings(rows):
    results = []

    for row in rows:
        stored = {
            "match_id": row["match_id"],
            "innings_number": row["innings_number"],
            "is_super_over": row["is_super_over"],
            "total_runs": row["total_runs"],
            "total_wickets": row["total_wickets"],
            "legal_balls_bowled": row["legal_balls_bowled"],
        }

        calculated = {
            "total_runs": row["total_runs_calculated"],
            "total_wickets": row["total_wickets_calculated"],
            "legal_balls_bowled": row["legal_balls_calculated"],
            "delivery_count": row["delivery_count"],
        }

        results.append(validate_innings(stored, calculated))

    return {
        "total_innings": len(results),
        "valid_innings": sum(r["is_valid"] for r in results),
        "invalid_innings": sum(not r["is_valid"] for r in results),
        "results": results,
    }
