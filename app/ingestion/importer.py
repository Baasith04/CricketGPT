
import hashlib
import json
from pathlib import Path

from psycopg.types.json import Jsonb

from app.database.connection import get_db_connection
from app.ingestion.parser import parse_match
from app.ingestion.resolver import resolve_team_id
from app.ingestion.validators.overs import overs_to_balls


BOWLER_CREDIT_DISMISSALS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket",
}


def delete_existing_match(cur, match_id):
    """
    Delete a match and its dependent records in bottom-up order.

    sync_files and sync_history are deliberately preserved.
    """
    delete_statements = [
        "DELETE FROM delivery_wickets WHERE match_id = %s",
        "DELETE FROM deliveries WHERE match_id = %s",
        "DELETE FROM match_awards WHERE match_id = %s",
        "DELETE FROM innings WHERE match_id = %s",
        "DELETE FROM match_players WHERE match_id = %s",
        "DELETE FROM match_teams WHERE match_id = %s",
        "DELETE FROM matches WHERE match_id = %s",
    ]

    for statement in delete_statements:
        cur.execute(statement, (match_id,))


def import_match(
    file_path: str | Path,
    update_existing: bool = False,
):
    """
    Import a new match or transactionally replace an existing match.

    update_existing=False:
        Reject duplicate matches.

    update_existing=True:
        Skip identical matches or replace changed matches.

    Returns:
        {
            "match_id": int,
            "status": "imported" | "updated" | "unchanged"
        }
    """
    file_path = Path(file_path)

    if not file_path.is_file():
        raise FileNotFoundError(f"Match file not found: {file_path}")

    # Read and parse the original Cricsheet file.
    raw_bytes = file_path.read_bytes()
    raw_data = json.loads(raw_bytes)
    match = parse_match(file_path)

    info = raw_data["info"]
    match_id = match["match_id"]
    teams = match["teams"]

    if len(teams) != 2 or len(set(teams)) != 2:
        raise ValueError("Expected exactly two distinct teams.")

    team_ids = {
        name: resolve_team_id(name)
        for name in teams
    }

    # Build a match-specific player lookup.
    player_lookup = {
        player["match_display_name"]: player["player_id"]
        for player in match["players"]
    }

    def get_player_id(name):
        player_id = player_lookup.get(name)

        if not player_id:
            raise ValueError(
                f"Player not found in match squad: {name}"
            )

        return player_id

    toss = info.get("toss", {})
    outcome = info.get("outcome", {})
    result_by = outcome.get("by", {})

    toss_winner = toss.get("winner")
    winner = outcome.get("winner")

    if toss_winner and toss_winner not in team_ids:
        raise ValueError("Unknown toss winner.")

    if winner and winner not in team_ids:
        raise ValueError("Unknown match winner.")

    if "runs" in result_by:
        result_type = "runs"

    elif "wickets" in result_by:
        result_type = "wickets"

    elif not winner:
        result_type = (
            "eliminator"
            if any(
                innings.get("super_over", False)
                for innings in info.get("innings", [])
            )
            else "no result"
        )

    elif outcome.get("result") == "tie":
        result_type = "tie"

    else:
        raise ValueError(f"Unsupported outcome: {outcome}")

    # Validate award recipients.
    registry = info.get("registry", {}).get("people", {})
    awards = []

    for name in info.get("player_of_match", []):
        player_id = registry.get(name)

        if not player_id:
            raise ValueError(
                f"Missing registry ID for award recipient: {name}"
            )

        awards.append((name, player_id))

    # Calculate source file hash and revision.
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    revision = raw_data.get("meta", {}).get("revision", 1)

    if (
        isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
    ):
        raise ValueError("Invalid Cricsheet revision.")

    # Everything below happens inside one database transaction.
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # Check and lock an existing match.
            cur.execute(
                """
                SELECT
                    m.match_id,
                    sf.file_sha256,
                    sf.cricsheet_revision
                FROM matches AS m
                LEFT JOIN sync_files AS sf
                    ON sf.match_id = m.match_id
                WHERE m.match_id = %s
                FOR UPDATE OF m
                """,
                (match_id,),
            )

            existing = cur.fetchone()
            was_existing = existing is not None

            if existing:
                existing_hash = existing[1]
                existing_revision = existing[2]

                if not update_existing:
                    raise ValueError(
                        f"Match {match_id} already exists. "
                        "Set update_existing=True to replace it."
                    )

                # Skip identical files without modifying the database.
                if (
                    existing_hash == file_hash
                    and existing_revision == revision
                ):
                    print(
                        f"Match {match_id} is already up to date."
                    )

                    return {
                        "match_id": match_id,
                        "status": "unchanged",
                    }

                print(f"Replacing corrected match {match_id}...")

                # Remove old match data in FK-safe order.
                delete_existing_match(cur, match_id)

            # 1. MATCH
            cur.execute(
                """
                INSERT INTO matches (
                    match_id,
                    season,
                    match_date,
                    venue,
                    city,
                    toss_winner_id,
                    toss_decision,
                    winner_id,
                    result_type,
                    result_method,
                    win_by_runs,
                    win_by_wickets,
                    raw_json
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    match_id,
                    match["season"],
                    match["dates"][0],
                    match["venue"] or "Unknown",
                    match["city"],
                    team_ids.get(toss_winner),
                    toss.get("decision"),
                    team_ids.get(winner),
                    result_type,
                    outcome.get("method"),
                    result_by.get("runs"),
                    result_by.get("wickets"),
                    Jsonb(raw_data),
                ),
            )

            # 2. MATCH TEAMS
            for number, team_name in enumerate(teams, start=1):
                cur.execute(
                    """
                    INSERT INTO match_teams (
                        match_id,
                        team_id,
                        team_number,
                        original_team_name
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        match_id,
                        team_ids[team_name],
                        number,
                        team_name,
                    ),
                )

            # 3. MATCH PLAYERS
            for player in match["players"]:
                cur.execute(
                    """
                    INSERT INTO match_players (
                        match_id,
                        player_id,
                        team_id,
                        match_display_name
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        match_id,
                        player["player_id"],
                        team_ids[player["team_name"]],
                        player["match_display_name"],
                    ),
                )

            # 4. MATCH AWARDS
            for name, player_id in awards:
                cur.execute(
                    """
                    INSERT INTO match_awards (
                        match_id,
                        award_name,
                        player_id,
                        recipient_name
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        match_id,
                        "Player of the Match",
                        player_id,
                        name,
                    ),
                )

            # 5. INNINGS
            for innings in match["innings"]:
                batting_team = innings["batting_team"]

                if batting_team not in team_ids:
                    raise ValueError(
                        f"Unknown batting team: {batting_team}"
                    )

                bowling_team = next(
                    team for team in teams
                    if team != batting_team
                )

                deliveries = innings["deliveries"]

                total_runs = sum(
                    delivery["total_runs"]
                    for delivery in deliveries
                )

                total_wickets = sum(
                    1
                    for delivery in deliveries
                    for wicket in delivery["wickets"]
                    if wicket["dismissal_kind"] != "retired hurt"
                )

                legal_balls = sum(
                    1
                    for delivery in deliveries
                    if delivery["wides"] == 0
                    and delivery["noballs"] == 0
                )

                target = innings.get("target") or {}

                target_runs = target.get("runs")
                target_overs = target.get("overs")

                # Retains the existing target-overs conversion.
                # This needs separate validation against Cricsheet's
                # target.overs representation before bulk importing.
                target_legal_balls = (
                overs_to_balls(target_overs)
                if target_overs is not None
                else None
                )

                cur.execute(
                    """
                    INSERT INTO innings (
                        match_id,
                        innings_number,
                        batting_team_id,
                        bowling_team_id,
                        is_super_over,
                        target_runs,
                        target_legal_balls,
                        total_runs,
                        total_wickets,
                        legal_balls_bowled
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    RETURNING innings_id
                    """,
                    (
                        match_id,
                        innings["innings_number"],
                        team_ids[batting_team],
                        team_ids[bowling_team],
                        innings["is_super_over"],
                        target_runs,
                        target_legal_balls,
                        total_runs,
                        total_wickets,
                        legal_balls,
                    ),
                )

                innings_id = cur.fetchone()[0]

                # 6. DELIVERIES
                for delivery in deliveries:
                    batter_id = get_player_id(delivery["batter"])
                    bowler_id = get_player_id(delivery["bowler"])
                    non_striker_id = get_player_id(
                        delivery["non_striker"]
                    )

                    cur.execute(
                        """
                        INSERT INTO deliveries (
                            innings_id,
                            match_id,
                            over_number,
                            delivery_sequence,
                            batter_id,
                            bowler_id,
                            non_striker_id,
                            batter_name,
                            bowler_name,
                            non_striker_name,
                            batter_runs,
                            extra_runs,
                            total_runs,
                            wide_runs,
                            no_ball_runs,
                            leg_bye_runs,
                            bye_runs,
                            penalty_runs,
                            review
                        )
                        VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        RETURNING delivery_id
                        """,
                        (
                            innings_id,
                            match_id,
                            delivery["over_number"],
                            delivery["delivery_sequence"],
                            batter_id,
                            bowler_id,
                            non_striker_id,
                            delivery["batter"],
                            delivery["bowler"],
                            delivery["non_striker"],
                            delivery["batter_runs"],
                            delivery["extra_runs"],
                            delivery["total_runs"],
                            delivery["wides"],
                            delivery["noballs"],
                            delivery["legbyes"],
                            delivery["byes"],
                            delivery["penalty"],
                            (
                                Jsonb(delivery["review"])
                                if delivery["review"] is not None
                                else None
                            ),
                        ),
                    )

                    delivery_id = cur.fetchone()[0]

                    # 7. DELIVERY WICKETS
                    for wicket in delivery["wickets"]:
                        dismissal = wicket["dismissal_kind"]
                        player_out = wicket["player_out"]

                        cur.execute(
                            """
                            INSERT INTO delivery_wickets (
                                delivery_id,
                                match_id,
                                dismissal_kind,
                                player_dismissed_id,
                                player_dismissed_name,
                                is_bowler_credit,
                                fielders
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                delivery_id,
                                match_id,
                                dismissal,
                                get_player_id(player_out),
                                player_out,
                                dismissal in BOWLER_CREDIT_DISMISSALS,
                                Jsonb(wicket["fielders"]),
                            ),
                        )

            # 8. SYNC FILE TRACKING
            # Insert new tracking record or update existing record.
            cur.execute(
                """
                INSERT INTO sync_files (
                    match_id,
                    file_name,
                    file_sha256,
                    cricsheet_revision,
                    status,
                    last_synced_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (match_id)
                DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    file_sha256 = EXCLUDED.file_sha256,
                    cricsheet_revision = EXCLUDED.cricsheet_revision,
                    status = EXCLUDED.status,
                    last_synced_at = NOW()
                """,
                (
                    match_id,
                    file_path.name,
                    file_hash,
                    revision,
                    "synced",
                ),
            )

        # Commit only after every insert and sync record succeeds.
        conn.commit()

    status = "updated" if was_existing else "imported"

    print(f"Match {match_id} {status} successfully.")
    print("Teams:", len(teams))
    print("Players:", len(match["players"]))
    print("Innings:", len(match["innings"]))
    print("Awards:", len(awards))
    print("Source file:", file_path.name)

    return {
        "match_id": match_id,
        "status": status,
    }
