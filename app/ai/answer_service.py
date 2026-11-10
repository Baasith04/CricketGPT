
from typing import Any, Dict, List, Optional

from app.ai.cutoff import (
    get_knowledge_cutoff_date,
    get_knowledge_cutoff_season,
    season_to_year,
)
from app.ai.llm.client import generate_response
from app.ai.prompts.system_prompt import CRICKETGPT_SYSTEM_PROMPT
from app.rag.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.matches.match_service import (
    PLAYOFF_STAGE_LABELS,
    get_latest_season,
    get_match_details,
    get_match_result,
    get_season_winner,
    normalize_playoff_stage,
    resolve_playoff_match,
)
from app.services.statistics.leaderboard_service import (
    get_batting_leaderboard,
    get_bowling_leaderboard,
    get_best_bowling_figures,
    get_highest_individual_scores,
)
from app.services.statistics.advanced_stats_service import (
    find_matches_by_filter,
    get_biggest_victories,
    get_extras_and_dismissals_summary,
    get_highest_successful_chases,
    get_match_awards,
    get_match_last_over,
    get_most_sixes_in_innings,
    get_phase_statistics,
    get_player_season_breakdown,
    get_team_totals_records,
)
from app.services.matches.scorecard_service import (
    get_match_scorecard,
    get_match_wickets,
)
from app.services.players.player_service import get_player_batting_stats
from app.services.players.bowling_service import get_player_bowling_stats
from app.services.players.player_comparison_service import compare_players
from app.services.teams.team_statistics_service import (
    get_individual_team_statistics,
    get_team_head_to_head,
    get_team_runs_leaderboard,
    get_team_versus_matches,
    get_teams_overall_statistics,
)
from app.rag.pipeline.rag_pipeline import answer_rag_question


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
    min_balls: int = None,
) -> str:
    """Return leaderboard results calculated directly by Supabase."""

    rate_categories = {"economy", "average", "strike_rate"}
    if min_balls is None:
        effective_min_balls = (
            (60 if season else 300) if category in rate_categories else 0
        )
    else:
        effective_min_balls = min_balls

    if question_type == "best_bowling":
        rows = get_best_bowling_figures(
            season=season,
            limit=limit,
        )

    elif question_type == "bowling":
        kwargs = {
            "category": category,
            "season": season,
            "limit": limit,
        }
        if effective_min_balls > 0:
            kwargs["min_balls"] = effective_min_balls
        rows = get_bowling_leaderboard(**kwargs)

    elif question_type == "batting":
        kwargs = {
            "category": category,
            "season": season,
            "limit": limit,
        }
        if effective_min_balls > 0:
            kwargs["min_balls"] = effective_min_balls
        rows = get_batting_leaderboard(**kwargs)

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
            "strike_rate": ("Bowling strike rate", "bowling_strike_rate"),
            "five_wickets": ("5-Wicket Hauls", "five_wickets"),
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
            "centuries": ("Centuries (100s)", "centuries"),
            "fifties": ("Half-centuries (50s)", "fifties"),
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

    if effective_min_balls > 0:
        lines.extend([
            "",
            f"Qualification filter: minimum {effective_min_balls} balls.",
        ])

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
    """Format a match scorecard (batting, bowling, extras, fall of wickets, result) from SQL."""

    scorecard = get_match_scorecard(match_id)

    if scorecard is None or (not scorecard.get("innings") and not scorecard.get("super_overs")):
        return f"No scorecard found for match {match_id}."

    wickets_by_innings: Dict[tuple[bool, int], List[Dict[str, Any]]] = {}
    try:
        wickets_data = get_match_wickets(match_id)
    except Exception:
        wickets_data = None
    if isinstance(wickets_data, dict):
        for inn_w in wickets_data.get("innings") or []:
            wickets_by_innings[(False, inn_w["innings_number"])] = inn_w.get("fall_of_wickets") or []
        for so_w in wickets_data.get("super_overs") or []:
            wickets_by_innings[(True, so_w["innings_number"])] = so_w.get("fall_of_wickets") or []

    match_meta = scorecard.get("match") or {}
    season_val = match_meta.get("season")
    stage_val = match_meta.get("stage")
    heading_bits = [f"IPL {season_val}" if season_val else "IPL"]
    if stage_val:
        heading_bits.append(str(stage_val))
    heading_bits.append(f"Match {match_id} - Scorecard")

    lines = [
        f"## {' '.join(heading_bits)}",
        "",
    ]

    meta_lines = _format_match_metadata_lines(match_meta)
    lines.extend(meta_lines)
    if meta_lines:
        lines.append("")

    def format_innings(innings, heading, fow_list=None):
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

        if fow_list:
            fow_parts = [
                f"{w['wicket_number']}-{w['score']} ({w['player_name']}, {w['overs']} ov)"
                for w in fow_list
            ]
            lines.append(f"**Fall of wickets:** {', '.join(fow_parts)}")
            lines.append("")

    for innings in scorecard["innings"]:
        heading = (
            f"Innings {innings['innings_number']} - "
            f"{innings['batting_team']}"
        )
        format_innings(
            innings,
            heading,
            fow_list=wickets_by_innings.get((False, innings["innings_number"])),
        )

    for innings in scorecard["super_overs"]:
        heading = (
            f"Super Over {innings['innings_number']} - "
            f"{innings['batting_team']}"
        )
        format_innings(
            innings,
            heading,
            fow_list=wickets_by_innings.get((True, innings["innings_number"])),
        )

    lines.extend([
        "---",
        "Source: CricketGPT historical IPL database (Supabase).",
        "Statistics are calculated from recorded match deliveries.",
    ])

    return "\n".join(lines)


def _format_match_metadata_lines(match_meta: Dict[str, Any]) -> List[str]:
    """Build standardized Fixture, Date, Venue, Toss, and Result lines from match metadata."""
    meta_lines: List[str] = []
    teams_meta = match_meta.get("teams") or []
    if teams_meta:
        fixture = " vs ".join(t["team_name"] for t in teams_meta if t.get("team_name"))
        if fixture:
            meta_lines.append(f"**Fixture:** {fixture}")
    if match_meta.get("match_date"):
        meta_lines.append(f"**Date:** {match_meta['match_date']}")
    if match_meta.get("venue"):
        city = match_meta.get("city")
        venue_str = (
            f"{match_meta['venue']}, {city}"
            if city and city.lower() not in str(match_meta["venue"]).lower()
            else str(match_meta["venue"])
        )
        meta_lines.append(f"**Venue:** {venue_str}")
    toss_meta = match_meta.get("toss") or {}
    if toss_meta.get("toss_winner_name"):
        meta_lines.append(
            f"**Toss:** {toss_meta['toss_winner_name']} won the toss and elected to "
            f"{toss_meta.get('toss_decision') or 'play'}"
        )
    result_meta = match_meta.get("result") or {}
    if result_meta.get("summary"):
        meta_lines.append(f"**Result:** {result_meta['summary']}")
    return meta_lines


def _format_playoff_match_summary(match_id: int, fallback_stage_label: Optional[str] = None) -> str:
    """Format verified SQL match details (teams, date, venue, toss, result) for a resolved match."""
    match_meta = get_match_details(match_id)
    if not match_meta:
        return f"No database record found for match {match_id}."

    season_val = match_meta.get("season")
    stage_val = match_meta.get("stage") or fallback_stage_label
    heading_bits = [f"IPL {season_val}" if season_val else "IPL"]
    if stage_val:
        heading_bits.append(str(stage_val))
    heading_bits.append(f"(Match {match_id})")

    lines = [f"## {' '.join(heading_bits)}", ""]
    if stage_val:
        lines.append(f"**Stage:** {stage_val}")
    lines.extend(_format_match_metadata_lines(match_meta))
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def _dispatch_match_detail(
    match_id: int,
    detail_type: str,
    stage_label: Optional[str] = None,
) -> str:
    """Dispatch a resolved match ID to the requested SQL detail formatter."""
    if detail_type == "wickets":
        return answer_wickets_question(match_id)
    if detail_type == "last_over":
        return answer_last_over_question(match_id)
    if detail_type == "potm":
        return answer_match_awards_question(match_id=match_id)
    if detail_type == "summary":
        return _format_playoff_match_summary(match_id, fallback_stage_label=stage_label)
    return answer_scorecard_question(match_id)


def answer_season_final_detail_question(season: str, detail_type: str = "scorecard") -> str:
    """Resolve an IPL season final via SQL and return its scorecard, wickets, or last over."""
    if not season or not str(season).strip():
        return "Please specify an IPL season to look up the final match."

    result = get_season_winner(str(season).strip())
    if result is None or not result.get("match_id"):
        return f"No IPL final match record was found in the database for season {season}."

    return _dispatch_match_detail(int(result["match_id"]), detail_type, stage_label="Final")


def answer_playoff_match_question(
    season: str,
    stage: str,
    detail_type: str = "scorecard",
) -> str:
    """Resolve an IPL playoff match via SQL stage metadata and format the requested detail."""
    canonical_stage = normalize_playoff_stage(stage)
    stage_label = PLAYOFF_STAGE_LABELS.get(canonical_stage or "", "playoff match")

    if not season or not str(season).strip():
        return (
            f"Please specify the IPL season for {stage_label} "
            f"(for example: 'Give me the IPL 2024 {stage_label} scorecard')."
        )

    if canonical_stage is None:
        return (
            "Please specify which playoff stage you want: "
            "Qualifier 1, Qualifier 2, Eliminator, or Final."
        )

    clean_season = str(season).strip()
    resolution = resolve_playoff_match(clean_season, canonical_stage)
    status = resolution.get("status")

    if status == "not_found":
        return (
            f"No {stage_label} match record was found in the database for IPL {clean_season}. "
            "(Note: early IPL seasons 2008-2010 used Semi Finals instead of Qualifier/Eliminator stages.) "
            "Please verify the season and stage or provide a specific match ID or date."
        )

    if status == "ambiguous":
        candidates = ", ".join(
            f"Match {m['match_id']} ({m['match_date']})"
            for m in resolution.get("matches") or []
        )
        return (
            f"Multiple {stage_label} records were found for IPL {clean_season} ({candidates}). "
            "Please specify a match ID or match date to view the exact match."
        )

    matched = resolution.get("match") or {}
    match_id = matched.get("match_id")
    if not match_id:
        return f"No {stage_label} match record was found in the database for IPL {clean_season}."

    return _dispatch_match_detail(
        int(match_id),
        detail_type,
        stage_label=matched.get("stage") or stage_label,
    )


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


def answer_player_question(player_name: str, season: str = None) -> str:
    """Format individual player batting and bowling statistics from verified SQL data."""

    if not player_name or not player_name.strip():
        return "Please provide a player name."

    if season:
        batting_rows = get_player_batting_stats(player_name, season=season)
        bowling_rows = get_player_bowling_stats(player_name, season=season)
    else:
        batting_rows = get_player_batting_stats(player_name)
        bowling_rows = get_player_bowling_stats(player_name)

    if not batting_rows and not bowling_rows:
        scope = f" in IPL {season}" if season else ""
        return (
            f"No IPL statistics found for player matching '{player_name}'{scope}. "
            "Check the spelling or try using the Cricsheet format (e.g. 'V Kohli')."
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

    heading_scope = f"IPL {season} Statistics" if season else "IPL Career Statistics"
    lines = [
        f"## {heading_scope} — {resolved_name}",
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
            f"| Fours | {b.get('fours', 0)} |",
            f"| Sixes | {b.get('sixes', 0)} |",
            f"| 50s / 100s | {b.get('fifties', 0)} / {b.get('hundreds', 0)} |",
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


def answer_team_question(team_identifier: str, season: str = None) -> str:
    """Format individual team statistics (all-time or for a specific season) from SQL."""

    if not team_identifier or not team_identifier.strip():
        return "Please provide a team name or identifier."

    try:
        if season:
            stats = get_individual_team_statistics(team_identifier, season=season)
        else:
            stats = get_individual_team_statistics(team_identifier)
    except ValueError as exc:
        return f"Team lookup error: {exc}"

    if stats is None:
        return (
            f"No IPL statistics found for team matching '{team_identifier}'. "
            "Try using the full name (e.g. 'Mumbai Indians') or short code (e.g. 'MI')."
        )

    if season and stats.get("matches_played", 0) == 0:
        return f"No IPL {season} match records found for {stats['team_name']}."

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
    heading = (
        f"## IPL {season} Team Statistics — {stats['team_name']}"
        if season
        else f"## IPL Team Statistics — {stats['team_name']}"
    )

    lines = [
        heading,
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


def answer_highest_individual_scores_question(
    season: str = None,
    limit: int = 10,
) -> str:
    """Format top single-innings individual batting scores from SQL."""
    rows = get_highest_individual_scores(season=season, limit=limit)
    if not rows:
        scope = f" in IPL {season}" if season else ""
        return f"No individual innings score records found{scope}."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## Highest Individual IPL Scores{scope}",
        "",
        "Rank | Player | Score | Balls | 4s | 6s | SR | Opponent | Season",
        "--- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---",
    ]
    for idx, row in enumerate(rows, start=1):
        not_out = "" if row.get("is_out") else "*"
        lines.append(
            f"{idx} | {row['player_name']} | {row['runs']}{not_out} | "
            f"{row['balls_faced']} | {row['fours']} | {row['sixes']} | "
            f"{row['strike_rate']} | {row['opponent']} | {row['season']}"
        )
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_boundaries_combined_question(
    season: str = None,
    limit: int = 10,
) -> str:
    """Return leaders for both sixes and fours when a query asks for both."""
    sixes_rows = get_batting_leaderboard(category="sixes", season=season, limit=limit)
    fours_rows = get_batting_leaderboard(category="fours", season=season, limit=limit)

    if not sixes_rows and not fours_rows:
        return "No boundary records found."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## IPL Sixes & Fours Leaders{scope}",
        "",
        "### Most Sixes",
        "",
        "Rank | Player | Sixes | Matches",
        "--- | --- | ---: | ---:",
    ]
    for idx, r in enumerate(sixes_rows, start=1):
        lines.append(f"{idx} | {r['player_name']} | {r['sixes']} | {r['matches_played']}")

    lines.extend([
        "",
        "### Most Fours",
        "",
        "Rank | Player | Fours | Matches",
        "--- | --- | ---: | ---:",
    ])
    for idx, r in enumerate(fours_rows, start=1):
        lines.append(f"{idx} | {r['player_name']} | {r['fours']} | {r['matches_played']}")

    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_player_comparison_question(
    player_one: str,
    player_two: str,
    season: Optional[str] = None,
) -> str:
    """Compare two players side-by-side (career or single season) using verified SQL statistics."""
    if not player_one or not player_two:
        return "Please provide two player names to compare."

    try:
        comp = (
            compare_players(player_one, player_two, season=season)
            if season
            else compare_players(player_one, player_two)
        )
    except ValueError as exc:
        return f"Player comparison error: {exc}"

    p1 = comp["player_one"]
    p2 = comp["player_two"]
    b1 = p1["batting"]
    b2 = p2["batting"]
    w1 = p1.get("bowling") or {}
    w2 = p2.get("bowling") or {}

    name1 = b1["player_name"]
    name2 = b2["player_name"]

    heading_prefix = f"## IPL {season} Player Comparison" if season else "## IPL Player Comparison"
    lines = [
        f"{heading_prefix}: {name1} vs {name2}",
        "",
        "### Batting Comparison",
        "",
        f"| Stat | {name1} | {name2} |",
        "|---|---:|---:|",
        f"| Matches | {b1.get('matches_played', 0)} | {b2.get('matches_played', 0)} |",
        f"| Innings | {b1.get('innings_batted', 0)} | {b2.get('innings_batted', 0)} |",
        f"| Runs | {b1.get('total_runs', 0)} | {b2.get('total_runs', 0)} |",
        f"| Highest Score | {b1.get('highest_score', 0)} | {b2.get('highest_score', 0)} |",
        f"| Average | {b1.get('batting_average') or 'N/A'} | {b2.get('batting_average') or 'N/A'} |",
        f"| Strike Rate | {b1.get('strike_rate', 0)} | {b2.get('strike_rate', 0)} |",
        f"| Fours | {b1.get('fours', 0)} | {b2.get('fours', 0)} |",
        f"| Sixes | {b1.get('sixes', 0)} | {b2.get('sixes', 0)} |",
        f"| 50s / 100s | {b1.get('fifties', 0)} / {b1.get('hundreds', 0)} | {b2.get('fifties', 0)} / {b2.get('hundreds', 0)} |",
        "",
        "### Bowling Comparison",
        "",
        f"| Stat | {name1} | {name2} |",
        "|---|---:|---:|",
        f"| Wickets | {w1.get('wickets', 0)} | {w2.get('wickets', 0)} |",
        f"| Economy | {w1.get('economy', 'N/A')} | {w2.get('economy', 'N/A')} |",
        f"| Bowling Average | {w1.get('bowling_average') or 'N/A'} | {w2.get('bowling_average') or 'N/A'} |",
        "",
        "---",
        "Source: CricketGPT historical IPL database (Supabase).",
    ]
    return "\n".join(lines)


def answer_player_season_breakdown_question(player_name: str) -> str:
    """Format a player's season-by-season IPL batting and bowling record."""
    if not player_name or not player_name.strip():
        return "Please provide a player name."

    data = get_player_season_breakdown(player_name)
    seasons = data.get("seasons", [])
    if not seasons:
        return f"No season-wise IPL records found for '{player_name}'."

    lines = [
        f"## Season-by-Season IPL Performance — {data['player_name']}",
        "",
        "| Season | Matches | Innings | Runs | HS | SR | 4s | 6s | Wickets | Econ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in seasons:
        lines.append(
            f"| {s['season']} | {s['matches']} | {s['innings_batted']} | "
            f"{s['runs']} | {s['highest_score']} | {s['strike_rate'] or 'N/A'} | "
            f"{s['fours']} | {s['sixes']} | {s['wickets']} | {s['economy'] or 'N/A'} |"
        )
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_team_runs_leaderboard_question(
    season: str = None,
    limit: int = 15,
) -> str:
    """Format teams ranked by total runs scored."""
    rows = get_team_runs_leaderboard(season=season, limit=limit)
    if not rows:
        return "No team run-scoring records found."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## IPL Teams by Total Runs Scored{scope}",
        "",
        "Rank | Team | Short | Matches | Innings | Total Runs | Run Rate",
        "--- | --- | --- | ---: | ---: | ---: | ---:",
    ]
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"{idx} | {r['team_name']} | {r['short_code']} | "
            f"{r['matches_played']} | {r['innings_batted']} | "
            f"{r['total_runs']} | {r['run_rate']}"
        )
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_most_titles_question() -> str:
    """Rank IPL franchises by championship titles won."""
    teams = get_teams_overall_statistics()
    if not teams:
        return "No team championship records found."

    ranked = sorted(
        teams,
        key=lambda t: (-t.get("championship_titles", 0), -t.get("wins", 0)),
    )
    lines = [
        "## IPL Championship Titles by Team",
        "",
        "Rank | Team | Short | Titles | Wins | Matches",
        "--- | --- | --- | ---: | ---: | ---:",
    ]
    for idx, t in enumerate(ranked, start=1):
        lines.append(
            f"{idx} | {t['team_name']} | {t['short_code']} | "
            f"{t['championship_titles']} | {t['wins']} | {t['matches_played']}"
        )
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_match_by_date_question(
    match_date,
    team_one: str = None,
    team_two: str = None,
    wants_scorecard: bool = False,
    wants_wickets: bool = False,
    wants_last_over: bool = False,
    wants_potm: bool = False,
) -> str:
    """Resolve match(es) on a specific date and return result/scorecard/wickets/POTM/last over."""
    try:
        matches = find_matches_by_filter(
            team_one=team_one,
            team_two=team_two,
            match_date=match_date,
        )
    except ValueError as exc:
        return f"Match lookup error: {exc}"

    if not matches:
        return f"No IPL matches found on {match_date}."

    if len(matches) == 1:
        match_id = matches[0]["match_id"]
        if wants_scorecard:
            return answer_scorecard_question(match_id)
        if wants_wickets:
            return answer_wickets_question(match_id)
        if wants_last_over:
            return answer_last_over_question(match_id)
        if wants_potm:
            return answer_match_awards_question(match_id=match_id)

    lines = [
        f"## IPL Match Results on {match_date}",
        "",
        "| Match ID | Teams | Winner | Margin | Venue |",
        "|---:|---|---|---|---|",
    ]
    for m in matches:
        winner = m.get("winner") or "No Result"
        margin = m.get("victory_margin") or "N/A"
        venue = m.get("venue") or "N/A"
        lines.append(
            f"| {m['match_id']} | {m['teams']} | {winner} | {margin} | {venue} |"
        )
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_match_awards_question(
    match_id: int = None,
    season: str = None,
    final_only: bool = False,
    limit: int = 10,
) -> str:
    """Format Player of the Match award info for a match, season final, or leaderboard."""
    rows = get_match_awards(
        match_id=match_id,
        season=season,
        final_only=final_only,
        limit=limit,
    )
    if not rows:
        if match_id:
            return f"No Player of the Match record found for match {match_id}."
        return "No Player of the Match records found."

    if match_id is not None or (final_only and season):
        first = rows[0]
        recipients = ", ".join(r["player_name"] for r in rows)
        return (
            f"## Player of the Match — Match {first['match_id']} (IPL {first['season']})\n\n"
            f"- **Fixture:** {first['teams']}\n"
            f"- **Date:** {first['match_date']}\n"
            f"- **Recipient:** **{recipients}**\n\n"
            "Source: CricketGPT historical IPL database (Supabase)."
        )

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## Most Player of the Match Awards{scope}",
        "",
        "Rank | Player | Awards",
        "--- | --- | ---: ",
    ]
    for idx, r in enumerate(rows, start=1):
        lines.append(f"{idx} | {r['player_name']} | {r['awards_count']}")
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_last_over_question(match_id: int) -> str:
    """Format ball-by-ball details of the final over of a match."""
    data = get_match_last_over(match_id)
    if not data or not data.get("deliveries"):
        return f"No last-over delivery records found for match {match_id}."

    innings_label = (
        f"Super Over (Innings {data['innings_number']})"
        if data["is_super_over"]
        else f"Innings {data['innings_number']}"
    )
    lines = [
        f"## Match {match_id} — Last Over ({innings_label}, Over {data['over_number']})",
        f"**Batting:** {data['batting_team']} | **Bowling:** {data['bowling_team']}",
        "",
        "| Ball | Batter | Bowler | Runs | Extras | Wicket |",
        "|---:|---|---|---:|---:|---|",
    ]
    for d in data["deliveries"]:
        wicket = d.get("wicket_text") or "-"
        lines.append(
            f"| {d['delivery_sequence']} | {d['batter_name']} | {d['bowler_name']} | "
            f"{d['total_runs']} | {d['extra_runs']} | {wicket} |"
        )
    lines.extend([
        "",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_highest_chases_question(season: str = None, limit: int = 10) -> str:
    rows = get_highest_successful_chases(season=season, limit=limit)
    if not rows:
        return "No successful run-chase records found."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## Highest Successful IPL Run Chases{scope}",
        "",
        "Rank | Chasing Team | Score | Target | Opponent | Season | Date",
        "--- | --- | ---: | ---: | --- | --- | ---",
    ]
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"{idx} | {r['chasing_team']} | {r['total_runs']}/{r['total_wickets']} | "
            f"{r.get('target_runs') or 'N/A'} | {r['bowling_team']} | "
            f"{r['season']} | {r['match_date']}"
        )
    lines.extend(["", "Source: CricketGPT historical IPL database (Supabase)."])
    return "\n".join(lines)


def answer_biggest_victories_question(
    by: str = "runs",
    season: str = None,
    limit: int = 10,
) -> str:
    rows = get_biggest_victories(by=by, season=season, limit=limit)
    if not rows:
        return f"No victory records by {by} found."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## Biggest IPL Victories by {by.title()}{scope}",
        "",
        f"Rank | Winner | Margin | Opponent | Season | Venue",
        f"--- | --- | ---: | --- | --- | ---",
    ]
    for idx, r in enumerate(rows, start=1):
        margin = (
            f"{r['win_by_runs']} runs"
            if by == "runs"
            else f"{r['win_by_wickets']} wickets"
        )
        lines.append(
            f"{idx} | {r['winner']} | {margin} | {r['opponent']} | {r['season']} | {r['venue']}"
        )
    lines.extend(["", "Source: CricketGPT historical IPL database (Supabase)."])
    return "\n".join(lines)


def answer_team_totals_question(
    highest: bool = True,
    season: str = None,
    limit: int = 10,
) -> str:
    rows = get_team_totals_records(highest=highest, season=season, limit=limit)
    if not rows:
        return "No team total records found."

    title = "Highest IPL Team Totals" if highest else "Lowest Completed IPL Team Totals"
    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## {title}{scope}",
        "",
        "Rank | Team | Score | Overs | Opponent | Season | Venue",
        "--- | --- | ---: | ---: | --- | --- | ---",
    ]
    for idx, r in enumerate(rows, start=1):
        balls = r["legal_balls_bowled"]
        overs = f"{balls // 6}.{balls % 6}"
        lines.append(
            f"{idx} | {r['batting_team']} | {r['total_runs']}/{r['total_wickets']} | "
            f"{overs} | {r['bowling_team']} | {r['season']} | {r['venue']}"
        )
    if not highest:
        lines.extend([
            "",
            "Note: Lowest totals include completed all-out or 20-over non-abandoned innings.",
        ])
    lines.extend(["", "Source: CricketGPT historical IPL database (Supabase)."])
    return "\n".join(lines)


def answer_most_sixes_innings_question(season: str = None, limit: int = 10) -> str:
    rows = get_most_sixes_in_innings(season=season, limit=limit)
    if not rows:
        return "No sixes-in-an-innings records found."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## Most Sixes in an IPL Innings{scope}",
        "",
        "Rank | Batter | Sixes | Runs (Balls) | Team | Opponent | Season",
        "--- | --- | ---: | ---: | --- | --- | ---",
    ]
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"{idx} | {r['player_name']} | {r['sixes']} | "
            f"{r['runs']} ({r['balls_faced']}) | {r['batting_team']} | "
            f"{r['opponent']} | {r['season']}"
        )
    lines.extend(["", "Source: CricketGPT historical IPL database (Supabase)."])
    return "\n".join(lines)


def answer_phase_stats_question(
    phase: str = "powerplay",
    stat_type: str = "batting",
    season: str = None,
    limit: int = 10,
) -> str:
    data = get_phase_statistics(
        phase=phase,
        stat_type=stat_type,
        season=season,
        limit=limit,
    )
    rows = data.get("rows", [])
    if not rows:
        return f"No {phase} {stat_type} records found."

    scope = f" - IPL {season}" if season else " - All IPL seasons"
    lines = [
        f"## {data['phase_label']} {stat_type.title()} Leaders{scope}",
        "",
    ]
    if stat_type == "bowling":
        lines.extend([
            "Rank | Bowler | Wickets | Overs | Runs | Economy",
            "--- | --- | ---: | ---: | ---: | ---:",
        ])
        for idx, r in enumerate(rows, start=1):
            balls = r["legal_balls"]
            overs = f"{balls // 6}.{balls % 6}"
            lines.append(
                f"{idx} | {r['player_name']} | {r['wickets']} | {overs} | "
                f"{r['runs_conceded']} | {r['economy']}"
            )
    else:
        lines.extend([
            "Rank | Batter | Runs | Balls | 4s | 6s | Strike Rate",
            "--- | --- | ---: | ---: | ---: | ---: | ---:",
        ])
        for idx, r in enumerate(rows, start=1):
            lines.append(
                f"{idx} | {r['player_name']} | {r['total_runs']} | {r['balls_faced']} | "
                f"{r['fours']} | {r['sixes']} | {r['strike_rate']}"
            )
    lines.extend([
        "",
        "Qualification filter: minimum 60 balls in this phase.",
        "Source: CricketGPT historical IPL database (Supabase).",
    ])
    return "\n".join(lines)


def answer_extras_dismissals_question(season: str = None) -> str:
    data = get_extras_and_dismissals_summary(season=season)
    extras = data["extras"]
    dismissals = data["dismissals"]
    scope = f" - IPL {season}" if season else " - All IPL seasons"

    lines = [
        f"## IPL Extras & Dismissals Summary{scope}",
        "",
        "### Extras Breakdown (regular innings)",
        "",
        "| Type | Runs |",
        "|---|---:|",
        f"| Total Extras | {extras['total_extras']} |",
        f"| Wides | {extras['wide_runs']} |",
        f"| No-balls | {extras['no_ball_runs']} |",
        f"| Leg-byes | {extras['leg_bye_runs']} |",
        f"| Byes | {extras['bye_runs']} |",
        f"| Penalty | {extras['penalty_runs']} |",
        "",
        "### Dismissals Breakdown",
        "",
        "| Dismissal Kind | Count | Bowler Credited |",
        "|---|---:|---|",
    ]
    for d in dismissals:
        credited = "Yes" if d["is_bowler_credit"] else "No"
        lines.append(f"| {d['dismissal_kind']} | {d['total_count']} | {credited} |")

    lines.extend(["", "Source: CricketGPT historical IPL database (Supabase)."])
    return "\n".join(lines)


def _build_post_cutoff_sql_snapshot(season: str) -> str:
    """Gather concise verified SQL summary context for a post-cutoff season."""
    blocks: List[str] = []
    winner = get_season_winner(season)
    if winner and winner.get("winner"):
        blocks.append(
            f"IPL {season} Champion: {winner['winner']} "
            f"(Final Match ID: {winner.get('match_id')}, Date: {winner.get('match_date')})"
        )

    top_bat = get_batting_leaderboard(category="runs", season=season, limit=5)
    if top_bat:
        bat_lines = [f"Top Run-Scorers (IPL {season}):"]
        for idx, r in enumerate(top_bat, start=1):
            bat_lines.append(
                f"{idx}. {r['player_name']}: {r.get('total_runs', 0)} runs "
                f"in {r.get('matches_played', 0)} matches"
            )
        blocks.append("\n".join(bat_lines))

    top_bowl = get_bowling_leaderboard(category="wickets", season=season, limit=5)
    if top_bowl:
        bowl_lines = [f"Top Wicket-Takers (IPL {season}):"]
        for idx, r in enumerate(top_bowl, start=1):
            bowl_lines.append(
                f"{idx}. {r['player_name']}: {r.get('wickets', 0)} wickets "
                f"in {r.get('matches_played', 0)} matches"
            )
        blocks.append("\n".join(bowl_lines))

    return "\n\n".join(blocks)


def answer_rag_narrative_question(
    question: str,
    season: str = None,
    doc_type: str = None,
    team: str = None,
    player: str = None,
) -> str:
    """Delegate narrative / rule / summary questions to the pgvector RAG pipeline."""
    sql_context = None
    if season is not None:
        cutoff_year = season_to_year(get_knowledge_cutoff_season())
        try:
            if season_to_year(season) > cutoff_year:
                snapshot = _build_post_cutoff_sql_snapshot(season)
                sql_context = snapshot or None
        except ValueError:
            sql_context = None

    return answer_rag_question(
        question=question,
        sql_context=sql_context,
        season=season,
        doc_type=doc_type,
        team=team,
        player=player,
    )


def answer_historical_llm_question(
    question: str,
    seasons: Optional[List[str]] = None,
    team_identifier: Optional[str] = None,
) -> str:
    """
    Answer historical / narrative IPL questions strictly within the application's
    configured knowledge boundary directly via Gemini (no RAG retrieval needed).
    """
    cutoff_season = get_knowledge_cutoff_season()
    cutoff_date = get_knowledge_cutoff_date().isoformat()
    season_scope = ", ".join(seasons) if seasons else f"up to IPL {cutoff_season}"

    prompt = f"""
{CRICKETGPT_SYSTEM_PROMPT}

KNOWLEDGE-BOUNDARY MODE (Within Application Boundary):
- This question refers strictly to historical IPL context within the application's
  configured boundary (<= IPL {cutoff_season} / {cutoff_date}; requested scope: {season_scope}).
- Answer the user's historical, tactical, or narrative question clearly using your
  established cricket knowledge for that historical period.
- Do NOT discuss events after IPL {cutoff_season} or invent unverified match ball-by-ball details.
- If a specific requested stat is not confirmed, state clearly that exact ball-by-ball
  verification can be queried from the statistical database.

User Question:
{question}
"""
    answer = generate_response(prompt).strip()
    footer = (
        f"\n\n### Sources\n"
        f"- **[Gemini Historical Knowledge]** Answered directly within the configured "
        f"application boundary (<= IPL {cutoff_season} / {cutoff_date})."
    )
    return f"{answer}{footer}"


def answer_post_cutoff_overview_question(
    question: str,
    season: Optional[str] = None,
) -> str:
    """
    Answer broad recent / post-cutoff questions (e.g. 'What happened in the latest IPL season?')
    using Supabase SQL leaders + champion plus pgvector RAG chunks grounded via Gemini.
    """
    effective_season = season
    if not effective_season:
        try:
            effective_season = get_latest_season()
        except Exception:
            effective_season = None

    if not effective_season:
        return (
            "No recent IPL season records are currently available in Supabase "
            "to answer this post-cutoff question reliably."
        )

    sql_snapshot = _build_post_cutoff_sql_snapshot(effective_season)
    return answer_rag_question(
        question=question,
        sql_context=sql_snapshot or None,
        season=effective_season,
    )


def answer_player_multi_season_comparison_question(
    question: str,
    player_name: str,
    seasons: List[str],
    cutoff_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Compare one player's performance across multiple IPL seasons (e.g. 2023 vs 2026)
    using authoritative SQL statistics per season plus RAG/historical narrative context.
    """
    if not player_name or not seasons:
        return "Please provide a player name and at least two seasons to compare."

    scope = (cutoff_info or {}).get("scope", "cross_cutoff")
    cutoff_season = get_knowledge_cutoff_season()
    cutoff_date = get_knowledge_cutoff_date().isoformat()
    post_seasons = (cutoff_info or {}).get("post_seasons", [])

    sql_rows: List[str] = [
        f"| Season | Matches | Innings | Runs | HS | Balls | Avg | SR | 4s | 6s | Wickets | Econ |",
        f"|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    resolved_name = player_name
    found_any = False

    for s in seasons:
        bat_list = get_player_batting_stats(player_name, season=s)
        bowl_list = get_player_bowling_stats(player_name, season=s)
        if not bat_list and not bowl_list:
            sql_rows.append(f"| {s} | No records | - | - | - | - | - | - | - | - | - | - |")
            continue

        found_any = True
        b = bat_list[0] if bat_list else {}
        resolved_name = b.get("player_name") or (bowl_list[0]["player_name"] if bowl_list else resolved_name)
        pid = b.get("player_id") or (bowl_list[0]["player_id"] if bowl_list else None)
        w = next((r for r in bowl_list if r["player_id"] == pid), {}) if pid else {}
        sql_rows.append(
            f"| {s} | {b.get('matches_played', w.get('matches_bowled', 0))} | "
            f"{b.get('innings_batted', 0)} | {b.get('total_runs', 0)} | "
            f"{b.get('highest_score', 0)} | {b.get('balls_faced', 0)} | "
            f"{b.get('batting_average') or 'N/A'} | {b.get('strike_rate', 0)} | "
            f"{b.get('fours', 0)} | {b.get('sixes', 0)} | "
            f"{w.get('wickets', 0)} | {w.get('economy', 'N/A')} |"
        )

    if not found_any:
        return (
            f"No IPL statistics found in Supabase for '{player_name}' "
            f"across seasons {', '.join(seasons)}."
        )

    sql_table = "\n".join([
        f"## Multi-Season Statistics — {resolved_name} ({', '.join(seasons)})",
        "",
        *sql_rows,
    ])

    # Retrieve RAG passages for post-cutoff seasons (or overall if none explicitly post-cutoff)
    rag_chunks: List[Dict[str, Any]] = []
    seen_chunk_ids = set()
    for target_s in (post_seasons or []):
        for ch in hybrid_retrieve(
            query=f"{resolved_name} IPL {target_s}",
            top_k=3,
            similarity_threshold=0.20,
            season=target_s,
            player=resolved_name,
        ):
            if ch["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(ch["chunk_id"])
                rag_chunks.append(ch)

    rag_blocks = [
        f"[S{idx}] {ch['title']} (IPL {ch.get('season', 'N/A')}): {ch['chunk_text']}"
        for idx, ch in enumerate(rag_chunks, start=1)
    ]

    prompt = f"""
{CRICKETGPT_SYSTEM_PROMPT}

MULTI-SEASON / CROSS-BOUNDARY PLAYER COMPARISON:
- Configured application knowledge boundary: <= IPL {cutoff_season} / {cutoff_date}.
- Temporal scope: {scope}.
- Use [SQL] below as the authoritative source of truth for ALL statistics in ALL seasons.
- Use [S1], [S2]... below for post-cutoff narrative context if available.
- Only use Gemini's historical cricket knowledge for context within <= IPL {cutoff_season},
  clearly marking any such points as [Gemini Historical Knowledge].
- Do NOT invent missing post-cutoff narrative details if not present in [SQL] or [S...].

[SQL] Verified Database Statistics:
{sql_table}

Retrieved Knowledge Chunks:
{chr(10).join(rag_blocks) if rag_blocks else 'None retrieved for requested seasons.'}

User Question:
{question}
"""
    synthesis = generate_response(prompt).strip()
    footer_lines = [
        "",
        "### Sources",
        "- **[SQL]** CricketGPT PostgreSQL / Supabase (verified delivery & season statistics)",
    ]
    if scope in {"within_cutoff", "cross_cutoff"}:
        footer_lines.append(
            f"- **[Gemini Historical Knowledge]** Pre-boundary context (<= IPL {cutoff_season} / {cutoff_date})"
        )
    for idx, ch in enumerate(rag_chunks, start=1):
        loc = ch.get("source_url") or ch.get("source_path") or ch.get("source_key")
        footer_lines.append(
            f"- **[S{idx}] {ch['title']}** (IPL {ch.get('season', 'N/A')}; "
            f"score: {ch.get('hybrid_score', 0):.3f}; source: `{loc}`)"
        )
    return f"{synthesis}\n" + "\n".join(footer_lines)


def answer_cross_boundary_question(
    question: str,
    seasons: Optional[List[str]] = None,
    team_identifiers: Optional[List[str]] = None,
    cutoff_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Answer cross-boundary questions spanning within-cutoff and post-cutoff IPL periods
    (e.g. 'Compare IPL 2016 and IPL 2026', 'Compare CSK in 2010 and 2026') by combining
    Gemini historical context for <= boundary with Supabase SQL + RAG for > boundary.
    """
    cutoff_season = get_knowledge_cutoff_season()
    cutoff_date = get_knowledge_cutoff_date().isoformat()
    within_seasons = list((cutoff_info or {}).get("within_seasons", []))
    post_seasons = list((cutoff_info or {}).get("post_seasons", []))

    target_seasons = list(seasons or [])
    if (cutoff_info or {}).get("is_relative_recent") and not post_seasons:
        try:
            latest = get_latest_season()
            if latest and latest not in target_seasons:
                target_seasons.append(latest)
                post_seasons.append(latest)
        except Exception:
            pass

    sql_blocks: List[str] = []
    if team_identifiers:
        for team_kw in team_identifiers[:2]:
            for s in (target_seasons or [None]):  # type: ignore[list-item]
                try:
                    stats = (
                        get_individual_team_statistics(team_kw, season=s)
                        if s
                        else get_individual_team_statistics(team_kw)
                    )
                except ValueError:
                    stats = None
                if stats and stats.get("matches_played", 0) > 0:
                    label = f"IPL {s}" if s else "All IPL Seasons"
                    sql_blocks.append(
                        f"{stats['team_name']} ({label}): "
                        f"Matches={stats['matches_played']}, Wins={stats['wins']}, "
                        f"Losses={stats['losses']}, Win%={stats.get('win_percentage', 0):.2f}%, "
                        f"Titles={stats.get('championship_titles', 0)}"
                    )
    else:
        for s in target_seasons:
            snapshot = _build_post_cutoff_sql_snapshot(s)
            if snapshot:
                sql_blocks.append(snapshot)

    rag_chunks: List[Dict[str, Any]] = []
    seen_chunk_ids = set()
    rag_search_seasons = post_seasons if post_seasons else [None]
    for s in rag_search_seasons:
        for ch in hybrid_retrieve(
            query=question,
            top_k=3,
            similarity_threshold=0.20,
            season=s,
        ):
            if ch["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(ch["chunk_id"])
                rag_chunks.append(ch)

    if not sql_blocks and not rag_chunks and post_seasons:
        return (
            f"Reliable post-cutoff Supabase data for IPL {', '.join(post_seasons)} "
            f"could not be found to complete this cross-period comparison."
        )

    rag_blocks = [
        f"[S{idx}] {ch['title']} (IPL {ch.get('season', 'N/A')}): {ch['chunk_text']}"
        for idx, ch in enumerate(rag_chunks, start=1)
    ]

    within_label = ", ".join(within_seasons) if within_seasons else f"<= IPL {cutoff_season}"
    post_label = ", ".join(post_seasons) if post_seasons else f"> IPL {cutoff_season}"

    prompt = f"""
{CRICKETGPT_SYSTEM_PROMPT}

CROSS-BOUNDARY SYNTHESIS MODE:
- Configured application knowledge boundary: <= IPL {cutoff_season} / {cutoff_date}.
- Historical period ({within_label}): You may use verified [SQL] facts below together with your
  historical cricket knowledge, clearly tagging historical narrative claims with [Gemini Historical Knowledge].
- Post-boundary period ({post_label}): You MUST rely STRICTLY on [SQL] and retrieved [S1], [S2]...
  passages below. Do NOT invent or assume any post-boundary statistics or results not supplied.
- Clearly distinguish the two sources in your comparison.

[SQL] Verified Supabase Database Facts:
{chr(10).join(sql_blocks) if sql_blocks else 'No matching SQL records.'}

Retrieved Supabase RAG Passages:
{chr(10).join(rag_blocks) if rag_blocks else 'None retrieved.'}

User Question:
{question}
"""
    answer = generate_response(prompt).strip()
    footer_lines = ["", "### Sources"]
    footer_lines.append(
        f"- **[Gemini Historical Knowledge]** Historical context within application boundary "
        f"(<= IPL {cutoff_season} / {cutoff_date})"
    )
    if sql_blocks:
        footer_lines.append(
            "- **[SQL]** CricketGPT PostgreSQL / Supabase (verified post-boundary & historical statistics)"
        )
    for idx, ch in enumerate(rag_chunks, start=1):
        loc = ch.get("source_url") or ch.get("source_path") or ch.get("source_key")
        footer_lines.append(
            f"- **[S{idx}] {ch['title']}** (IPL {ch.get('season', 'N/A')}; "
            f"score: {ch.get('hybrid_score', 0):.3f}; source: `{loc}`)"
        )
    return f"{answer}\n" + "\n".join(footer_lines)


def answer_hybrid_team_question(
    question: str,
    team_identifier: str,
    season: str = None,
) -> str:
    """Combine SQL team statistics with retrieved RAG match/team documents."""
    sql_summary = answer_team_question(team_identifier, season=season)
    resolved_stats = (
        get_individual_team_statistics(team_identifier, season=season)
        if season
        else get_individual_team_statistics(team_identifier)
    )
    resolved_team_name = resolved_stats["team_name"] if resolved_stats else None
    return answer_rag_question(
        question=question,
        sql_context=sql_summary,
        season=season,
        team=resolved_team_name,
    )


def answer_hybrid_player_comparison_question(
    question: str,
    player_one: str,
    player_two: str,
    season: str = None,
) -> str:
    """
    Combine verified SQL player batting & bowling stats (career or season-filtered)
    with retrieved RAG context to generate a grounded explanation.
    """
    if season:
        b1_list = get_player_batting_stats(player_one, season=season)
        b2_list = get_player_batting_stats(player_two, season=season)
        w1_list = get_player_bowling_stats(player_one, season=season)
        w2_list = get_player_bowling_stats(player_two, season=season)
    else:
        b1_list = get_player_batting_stats(player_one)
        b2_list = get_player_batting_stats(player_two)
        w1_list = get_player_bowling_stats(player_one)
        w2_list = get_player_bowling_stats(player_two)

    if not b1_list or not b2_list:
        missing = player_one if not b1_list else player_two
        scope = f" in IPL {season}" if season else ""
        return f"No SQL statistics found for '{missing}'{scope} to compare."

    b1 = b1_list[0]
    b2 = b2_list[0]
    w1 = next((r for r in w1_list if r["player_id"] == b1["player_id"]), {})
    w2 = next((r for r in w2_list if r["player_id"] == b2["player_id"]), {})

    scope_label = f"IPL {season}" if season else "All IPL Seasons"
    sql_context = "\n".join([
        f"## {scope_label} Comparison: {b1['player_name']} vs {b2['player_name']}",
        "",
        f"| Stat | {b1['player_name']} | {b2['player_name']} |",
        "|---|---:|---:|",
        f"| Matches | {b1.get('matches_played', 0)} | {b2.get('matches_played', 0)} |",
        f"| Innings | {b1.get('innings_batted', 0)} | {b2.get('innings_batted', 0)} |",
        f"| Runs | {b1.get('total_runs', 0)} | {b2.get('total_runs', 0)} |",
        f"| Highest Score | {b1.get('highest_score', 0)} | {b2.get('highest_score', 0)} |",
        f"| Balls Faced | {b1.get('balls_faced', 0)} | {b2.get('balls_faced', 0)} |",
        f"| Batting Average | {b1.get('batting_average') or 'N/A'} | {b2.get('batting_average') or 'N/A'} |",
        f"| Strike Rate | {b1.get('strike_rate', 0)} | {b2.get('strike_rate', 0)} |",
        f"| Fours | {b1.get('fours', 0)} | {b2.get('fours', 0)} |",
        f"| Sixes | {b1.get('sixes', 0)} | {b2.get('sixes', 0)} |",
        f"| 50s / 100s | {b1.get('fifties', 0)} / {b1.get('hundreds', 0)} | {b2.get('fifties', 0)} / {b2.get('hundreds', 0)} |",
        f"| Bowling Wickets | {w1.get('wickets', 0)} | {w2.get('wickets', 0)} |",
    ])

    return answer_rag_question(
        question=question,
        sql_context=sql_context,
        season=season,
    )

