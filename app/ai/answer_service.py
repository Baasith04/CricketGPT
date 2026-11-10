
from app.ai.llm.client import generate_response
from app.ai.prompts.system_prompt import CRICKETGPT_SYSTEM_PROMPT
from app.services.matches.match_service import get_match_result
from app.services.matches.match_service import get_season_winner
from app.services.statistics.leaderboard_service import (
    get_batting_leaderboard,
    get_bowling_leaderboard,
    get_best_bowling_figures,
)
from app.services.matches.scorecard_service import (
    get_match_scorecard,
    get_match_wickets,
)
from app.services.players.player_service import get_player_batting_stats
from app.services.players.bowling_service import get_player_bowling_stats
from app.services.teams.team_statistics_service import (
    get_individual_team_statistics,
    get_team_head_to_head,
    get_team_versus_matches,
)


def answer_match_question(match_id: int, question: str) -> str:
    """Answer a user's question using verified SQL match data."""

    match = get_match_result(match_id)

    if match is None:
        return f"No database record found for match {match_id}."

    context = f"""
Verified match information from Supabase:

Match ID: {match['match_id']}
Season: {match['season']}
Date: {match['match_date']}
Winner: {match['winner']}
Result type: {match['result_type']}
Won by runs: {match['win_by_runs']}
Won by wickets: {match['win_by_wickets']}
Result method: {match['result_method']}
"""

    prompt = f"""
{CRICKETGPT_SYSTEM_PROMPT}

Answer the user's actual question using ONLY the supplied
database information.

{context}

User question:
{question}

Do not invent missing statistics.
If the database does not contain enough information,
clearly say so.
"""

    return generate_response(prompt)


def answer_leaderboard_question(
    category: str,
    question_type: str,
    season: str = None,
    limit: int = 10,
) -> str:
    """Return leaderboard results calculated directly by Supabase."""

    if question_type == "best_bowling":
        rows = get_best_bowling_figures(
            season=season,
            limit=limit,
        )

    elif question_type == "bowling":
        rows = get_bowling_leaderboard(
            category=category,
            season=season,
            limit=limit,
        )

    elif question_type == "batting":
        rows = get_batting_leaderboard(
            category=category,
            season=season,
            limit=limit,
        )

    else:
        return "Unsupported leaderboard question type."

    if not rows:
        scope = f" in IPL season {season}" if season else " in IPL"
        return f"No leaderboard records found{scope}."

    scope = f" - IPL {season}" if season else " - All IPL seasons"

    lines = [
        f"**IPL {question_type.replace('_', ' ').title()} Leaderboard{scope}**",
        "",
    ]

    # Best bowling figures
    if question_type == "best_bowling":
        lines.extend([
            "Rank | Player | Season | Match ID | Figures | Overs",
            "--- | --- | --- | --- | --- | ---:",
        ])

        for index, row in enumerate(rows, start=1):
            legal_balls = row["legal_balls"]
            overs = f"{legal_balls // 6}.{legal_balls % 6}"
            figures = f"{row['wickets']}/{row['runs_conceded']}"

            lines.append(
                f"{index} | {row['player_name']} | "
                f"{row['season']} | {row['match_id']} | "
                f"{figures} | {overs}"
            )

    # Bowling leaderboard
    elif question_type == "bowling":
        bowling_columns = {
            "wickets": ("Wickets", "wickets"),
            "economy": ("Economy", "economy"),
            "average": ("Bowling average", "bowling_average"),
            "strike_rate": (
                "Bowling strike rate",
                "bowling_strike_rate",
            ),
        }

        label, field = bowling_columns.get(
            category,
            ("Wickets", "wickets"),
        )

        lines.extend([
            f"Rank | Player | {label} | Matches",
            "--- | --- | ---: | ---:",
        ])

        for index, row in enumerate(rows, start=1):
            value = row.get(field)
            value = value if value is not None else "N/A"

            lines.append(
                f"{index} | {row['player_name']} | "
                f"{value} | {row['matches_played']}"
            )

    # Batting leaderboard
    else:
        batting_columns = {
            "runs": ("Runs", "total_runs"),
            "highest_score": ("Highest score", "highest_score"),
            "sixes": ("Sixes", "sixes"),
            "fours": ("Fours", "fours"),
            "average": ("Batting average", "batting_average"),
            "strike_rate": ("Strike rate", "strike_rate"),
        }

        label, field = batting_columns.get(
            category,
            ("Runs", "total_runs"),
        )

        lines.extend([
            f"Rank | Player | {label} | Matches",
            "--- | --- | ---: | ---:",
        ])

        for index, row in enumerate(rows, start=1):
            value = row.get(field)
            value = value if value is not None else "N/A"

            lines.append(
                f"{index} | {row['player_name']} | "
                f"{value} | {row['matches_played']}"
            )

    lines.extend([
        "",
        "Source: CricketGPT historical IPL statistics database (Supabase).",
        "These are calculated database results, not live statistics.",
    ])

    return "\n".join(lines)

    
def answer_season_winner_question(season: str) -> str:
    """Answer IPL season winner questions using verified database data."""

    result = get_season_winner(season)

    if result is None:
        return (
            f"No IPL final match record was found for season {season}."
        )

    if not result["winner"]:
        return (
            f"The IPL final for season {season} is recorded, "
            "but the winner is not available in the database."
        )

    return (
        f"The IPL {season} champion was **{result['winner']}**.\n\n"
        f"Final Match ID: {result['match_id']}\n"
        f"Final Date: {result['match_date']}\n"
        f"Source: CricketGPT historical IPL database (Supabase)."
    )


def answer_scorecard_question(match_id: int) -> str:
    """Format a match scorecard using verified SQL results."""

    scorecard = get_match_scorecard(match_id)

    if scorecard is None:
        return f"No scorecard found for match {match_id}."

    lines = [
        f"## IPL Match {match_id} - Scorecard",
        "",
    ]

    def format_innings(innings, heading):
        lines.append(f"### {heading}")
        lines.append(
            f"**{innings['batting_team']}: "
            f"{innings['total_runs']}/{innings['total_wickets']} "
            f"({innings['overs']} overs)**"
        )
        lines.append("")

        lines.extend([
            "**Batting**",
            "",
            "| Batter | Dismissal | R | B | 4s | 6s | SR |",
            "|---|---|---:|---:|---:|---:|---:|",
        ])

        for batter in innings["batting"]:
            lines.append(
                f"| {batter['player_name']} | {batter['dismissal']} "
                f"| {batter['runs']} | {batter['balls']} "
                f"| {batter['fours']} | {batter['sixes']} "
                f"| {batter['strike_rate']} |"
            )

        lines.extend([
            "",
            "**Bowling**",
            "",
            "| Bowler | Overs | Maidens | Runs | Wickets | Economy |",
            "|---|---:|---:|---:|---:|---:|",
        ])

        for bowler in innings["bowling"]:
            lines.append(
                f"| {bowler['player_name']} | {bowler['overs']} "
                f"| {bowler['maidens']} | {bowler['runs_conceded']} "
                f"| {bowler['wickets']} | {bowler['economy']} |"
            )

        extras = innings["extras"]

        lines.extend([
            "",
            f"**Extras:** {extras['total_extras']} "
            f"(Wides: {extras['wides']}, "
            f"No-balls: {extras['no_balls']}, "
            f"Byes: {extras['byes']}, "
            f"Leg-byes: {extras['leg_byes']}, "
            f"Penalty: {extras['penalty']})",
            "",
            f"**Total:** {innings['total_runs']}/"
            f"{innings['total_wickets']} "
            f"({innings['overs']} overs)",
            f"**Run rate:** {innings['run_rate']}",
            "",
        ])

    for innings in scorecard["innings"]:
        heading = (
            f"Innings {innings['innings_number']} - "
            f"{innings['batting_team']}"
        )
        format_innings(innings, heading)

    for innings in scorecard["super_overs"]:
        heading = (
            f"Super Over {innings['innings_number']} - "
            f"{innings['batting_team']}"
        )
        format_innings(innings, heading)

    lines.extend([
        "---",
        "Source: CricketGPT historical IPL database (Supabase).",
        "Statistics are calculated from recorded match deliveries.",
    ])

    return "\n".join(lines)


def answer_wickets_question(match_id: int) -> str:
    """Format fall-of-wickets information using verified SQL results."""

    result = get_match_wickets(match_id)

    if result is None:
        return f"No wicket records found for match {match_id}."

    lines = [
        f"## IPL Match {match_id} - Fall of Wickets",
        "",
    ]

    def format_wickets(innings, heading):
        lines.extend([
            f"### {heading}",
            "",
            f"**{innings['batting_team']}**",
            "",
            "| Wicket | Batter | Score | Overs | Dismissal |",
            "|---:|---|---:|---:|---|",
        ])

        for wicket in innings["fall_of_wickets"]:
            lines.append(
                f"| {wicket['wicket_number']} "
                f"| {wicket['player_name']} "
                f"| {wicket['score']} "
                f"| {wicket['overs']} "
                f"| {wicket['dismissal_kind']} |"
            )

        if not innings["fall_of_wickets"]:
            lines.append("No wickets recorded in this innings.")

        lines.append("")

    for innings in result["innings"]:
        heading = (
            f"Innings {innings['innings_number']} - "
            f"{innings['batting_team']}"
        )
        format_wickets(innings, heading)

    for innings in result["super_overs"]:
        heading = (
            f"Super Over {innings['innings_number']} - "
            f"{innings['batting_team']}"
        )
        format_wickets(innings, heading)

    lines.extend([
        "---",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])

    return "\n".join(lines)


def answer_player_question(player_name: str) -> str:
    """Format individual player batting and bowling statistics from verified SQL data."""

    if not player_name or not player_name.strip():
        return "Please provide a player name."

    batting_rows = get_player_batting_stats(player_name)
    bowling_rows = get_player_bowling_stats(player_name)

    if not batting_rows and not bowling_rows:
        return (
            f"No IPL statistics found for player matching '{player_name}'. "
            "Check the spelling or try using the abbreviated format, e.g. 'V Kohli'."
        )

    # Pair batting and bowling records for the same player_id to avoid
    # mismatching two different players when a surname matches multiple rows.
    if batting_rows:
        b = batting_rows[0]
        resolved_id = b["player_id"]
        resolved_name = b["player_name"]
        w = next(
            (row for row in bowling_rows if row["player_id"] == resolved_id),
            None,
        )
    else:
        b = None
        w = bowling_rows[0]
        resolved_name = w["player_name"]

    lines = [
        f"## IPL Career Statistics — {resolved_name}",
        "",
    ]

    # --- Batting ---
    if b:
        bat_avg = (
            b["batting_average"]
            if b.get("batting_average") is not None
            else "N/A"
        )
        lines.extend([
            "### Batting",
            "",
            "| Stat | Value |",
            "|---|---:|",
            f"| Matches | {b.get('matches_played', 0)} |",
            f"| Innings | {b.get('innings_batted', 0)} |",
            f"| Runs | {b.get('total_runs', 0)} |",
            f"| Highest score | {b.get('highest_score', 0)} |",
            f"| Balls faced | {b.get('balls_faced', 0)} |",
            f"| Dismissals | {b.get('dismissals', 0)} |",
            f"| Batting average | {bat_avg} |",
            f"| Strike rate | {b.get('strike_rate', 0)} |",
            "",
        ])
    else:
        lines.extend(["### Batting", "", "No batting records found.", ""])

    # --- Bowling ---
    if w:
        legal_balls = w.get("legal_balls", 0)
        overs_str = f"{legal_balls // 6}.{legal_balls % 6}"
        bowl_avg = (
            w["bowling_average"]
            if w.get("bowling_average") is not None
            else "N/A"
        )
        bowl_sr = (
            w["bowling_strike_rate"]
            if w.get("bowling_strike_rate") is not None
            else "N/A"
        )
        lines.extend([
            "### Bowling",
            "",
            "| Stat | Value |",
            "|---|---:|",
            f"| Matches | {w.get('matches_bowled', 0)} |",
            f"| Innings | {w.get('innings_bowled', 0)} |",
            f"| Overs | {overs_str} |",
            f"| Wickets | {w.get('wickets', 0)} |",
            f"| Runs conceded | {w.get('runs_conceded', 0)} |",
            f"| Economy | {w.get('economy', 0)} |",
            f"| Bowling average | {bowl_avg} |",
            f"| Bowling strike rate | {bowl_sr} |",
            "",
        ])
    else:
        lines.extend(["### Bowling", "", "No bowling records found.", ""])

    lines.extend([
        "---",
        "Source: CricketGPT historical IPL statistics database (Supabase).",
        "These are calculated database results, not live statistics.",
    ])

    return "\n".join(lines)


def answer_team_question(team_identifier: str) -> str:
    """Format individual team statistics from verified SQL data."""

    if not team_identifier or not team_identifier.strip():
        return "Please provide a team name or identifier."

    try:
        stats = get_individual_team_statistics(team_identifier)
    except ValueError as exc:
        return f"Team lookup error: {exc}"

    if stats is None:
        return (
            f"No IPL statistics found for team matching '{team_identifier}'. "
            "Try using the full name (e.g. 'Mumbai Indians') or short code (e.g. 'MI')."
        )

    legal_balls_faced = stats.get("legal_balls_faced", 0)
    legal_balls_bowled = stats.get("legal_balls_bowled", 0)
    overs_faced = f"{legal_balls_faced // 6}.{legal_balls_faced % 6}"
    overs_bowled = f"{legal_balls_bowled // 6}.{legal_balls_bowled % 6}"

    championship_seasons = stats.get("championship_seasons") or []
    titles_str = (
        ", ".join(str(s) for s in championship_seasons)
        if championship_seasons
        else "None"
    )

    lines = [
        f"## IPL Team Statistics — {stats['team_name']}",
        f"Short code: **{stats.get('short_code', 'N/A')}**",
        "",
        "### Match Record",
        "",
        "| Stat | Value |",
        "|---|---:|",
        f"| Matches played | {stats.get('matches_played', 0)} |",
        f"| Wins | {stats.get('wins', 0)} |",
        f"| Losses | {stats.get('losses', 0)} |",
        f"| Ties | {stats.get('ties', 0)} |",
        f"| No results | {stats.get('no_results', 0)} |",
        f"| Win percentage | {stats.get('win_percentage', 0.0):.2f}% |",
        f"| Championship titles | {stats.get('championship_titles', 0)} |",
        f"| Title seasons | {titles_str} |",
        "",
        "### Batting (regular innings)",
        "",
        "| Stat | Value |",
        "|---|---:|",
        f"| Innings batted | {stats.get('innings_batted', 0)} |",
        f"| Runs scored | {stats.get('runs_scored', 0)} |",
        f"| Wickets lost | {stats.get('wickets_lost', 0)} |",
        f"| Overs faced | {overs_faced} |",
        f"| Batting run rate | {stats.get('batting_run_rate', 0)} |",
        "",
        "### Bowling (regular innings)",
        "",
        "| Stat | Value |",
        "|---|---:|",
        f"| Innings bowled | {stats.get('innings_bowled', 0)} |",
        f"| Runs conceded | {stats.get('runs_conceded', 0)} |",
        f"| Wickets taken | {stats.get('wickets_taken', 0)} |",
        f"| Overs bowled | {overs_bowled} |",
        f"| Bowling economy | {stats.get('bowling_economy', 0)} |",
        "",
        "---",
        "Source: CricketGPT historical IPL statistics database (Supabase).",
        "These are calculated database results, not live statistics.",
    ]

    return "\n".join(lines)


def answer_head_to_head_question(team_one: str, team_two: str) -> str:
    """Format head-to-head record between two teams from verified SQL data."""

    if not team_one or not team_two:
        return "Please provide both team names for a head-to-head comparison."

    try:
        h2h = get_team_head_to_head(team_one, team_two)
    except ValueError as exc:
        return f"Head-to-head lookup error: {exc}"

    if h2h is None:
        return (
            f"No head-to-head records found between "
            f"'{team_one}' and '{team_two}'."
        )

    t1 = h2h.get("team_one", team_one)
    t2 = h2h.get("team_two", team_two)
    total = h2h.get("matches_played", 0)
    t1_wins = h2h.get("team_one_wins", 0)
    t2_wins = h2h.get("team_two_wins", 0)
    ties = h2h.get("ties", 0)
    no_results = h2h.get("no_results", 0)

    lines = [
        f"## IPL Head-to-Head: {t1} vs {t2}",
        "",
        "| Stat | Value |",
        "|---|---:|",
        f"| Matches played | {total} |",
        f"| {t1} wins | {t1_wins} |",
        f"| {t2} wins | {t2_wins} |",
        f"| Ties | {ties} |",
        f"| No results | {no_results} |",
        "",
        "---",
        "Source: CricketGPT historical IPL statistics database (Supabase).",
        "These are calculated database results, not live statistics.",
    ]

    return "\n".join(lines)


def answer_team_versus_matches_question(
    team_one: str,
    team_two: str,
    season: str = None,
) -> str:
    """Format all matches between two teams (optionally for a given season) from SQL."""

    if not team_one or not team_two:
        return "Please provide both team names to look up match results."

    try:
        data = get_team_versus_matches(team_one, team_two, season=season)
    except ValueError as exc:
        return f"Match lookup error: {exc}"

    t1 = data.get("team_one", team_one)
    t2 = data.get("team_two", team_two)
    resolved_season = data.get("season")
    matches = data.get("matches", [])

    scope_label = f"IPL {resolved_season}" if resolved_season else "IPL"

    if not matches:
        if resolved_season:
            return (
                f"No {scope_label} matches found between {t1} and {t2}."
            )
        return f"No IPL matches found between {t1} and {t2}."

    lines = [
        f"## {scope_label} Match Results: {t1} vs {t2}",
        "",
        f"Matches found: **{len(matches)}**",
        "",
        "| Date | Match ID | Teams | Winner | Margin | Venue |",
        "|---|---:|---|---|---|---|",
    ]

    for m in matches:
        match_date = m.get("match_date") or "N/A"
        match_id = m.get("match_id")
        teams = m.get("teams") or f"{t1} vs {t2}"
        winner = m.get("winner") or ("Tie" if m.get("is_super_over") else "No Result")
        margin = m.get("victory_margin") or "N/A"
        venue = m.get("venue") or "N/A"
        if m.get("city") and m["city"] not in venue:
            venue = f"{venue}, {m['city']}"

        lines.append(
            f"| {match_date} | {match_id} | {teams} | {winner} | {margin} | {venue} |"
        )

    lines.extend([
        "",
        "---",
        "Source: CricketGPT historical IPL database (Supabase).",
        "These are verified database match records, not live statistics.",
    ])

    return "\n".join(lines)

