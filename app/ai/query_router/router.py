from datetime import date
import re
from typing import Any, Dict, List, Optional, Tuple

from app.ai.answer_service import (
    answer_biggest_victories_question,
    answer_boundaries_combined_question,
    answer_cross_boundary_question,
    answer_extras_dismissals_question,
    answer_head_to_head_question,
    answer_highest_chases_question,
    answer_highest_individual_scores_question,
    answer_historical_llm_question,
    answer_hybrid_player_comparison_question,
    answer_hybrid_team_question,
    answer_last_over_question,
    answer_leaderboard_question,
    answer_match_awards_question,
    answer_match_by_date_question,
    answer_match_question,
    answer_most_sixes_innings_question,
    answer_most_titles_question,
    answer_phase_stats_question,
    answer_player_comparison_question,
    answer_player_multi_season_comparison_question,
    answer_player_question,
    answer_player_season_breakdown_question,
    answer_post_cutoff_overview_question,
    answer_rag_narrative_question,
    answer_scorecard_question,
    answer_season_winner_question,
    answer_team_question,
    answer_team_runs_leaderboard_question,
    answer_team_totals_question,
    answer_team_versus_matches_question,
    answer_wickets_question,
)
from app.ai.cutoff import (
    SEASON_ALIASES,
    classify_temporal_scope,
    normalize_season_token,
)
from app.services.matches.match_service import (
    get_first_match_id,
    get_latest_season,
)


FIRST_MATCH_PATTERNS = [
    "first match of ipl",
    "1st match of ipl",
    "opening match of ipl",
    "first ipl match",
    "inaugural ipl match",
]

# Known IPL team keywords / short codes / aliases (longest phrases first for regex alternation).
IPL_TEAM_KEYWORDS = [
    "royal challengers bengaluru",
    "royal challengers bangalore",
    "rising pune supergiants",
    "rising pune supergiant",
    "kolkata knight riders",
    "lucknow super giants",
    "chennai super kings",
    "sunrisers hyderabad",
    "kochi tuskers kerala",
    "royal challengers",
    "delhi daredevils",
    "rajasthan royals",
    "kings xi punjab",
    "mumbai indians",
    "delhi capitals",
    "deccan chargers",
    "gujarat titans",
    "gujarat lions",
    "pune warriors",
    "kochi tuskers",
    "punjab kings",
    "pbks",
    "kxip",
    "csk",
    "rcb",
    "kkr",
    "srh",
    "lsg",
    "rps",
    "ktk",
    "pwi",
    "dec",
    "mi",
    "dc",
    "rr",
    "gt",
    "gl",
]

_TEAM_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in IPL_TEAM_KEYWORDS) + r")\b"
)

_LEADERBOARD_GUARD_TERMS = [
    "leaderboard",
    "most runs",
    "most wickets",
    "highest run",
    "highest wicket",
    "highest score",
    "high score",
    "highest batting average",
    "best batting average",
    "highest average",
    "best bowling average",
    "highest strike rate",
    "best strike rate",
    "best bowling strike rate",
    "orange cap",
    "purple cap",
    "best economy",
    "most economical",
    "most sixes",
    "most fours",
    "most centuries",
    "most hundreds",
    "most fifties",
    "five-wicket",
    "5-wicket",
    "5 wicket",
    "five wicket",
]

_GENERIC_PLAYER_REJECTS = {
    "ipl",
    "ipl history",
    "cricket",
    "team",
    "teams",
    "match",
    "matches",
    "season",
    "batting",
    "bowling",
    "career",
    "statistics",
    "stats",
    "record",
    "records",
    "all",
    "overall",
    "powerplay",
    "middle",
    "death",
    "scorecard",
    "wickets",
    "runs",
}

_DATE_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _extract_date(normalized: str) -> Optional[date]:
    """Extract an explicit calendar date (YYYY-MM-DD, DD/MM/YYYY, or Month DD, YYYY)."""
    # 1. ISO YYYY-MM-DD
    iso_m = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", normalized)
    if iso_m:
        try:
            return date(int(iso_m.group(1)), int(iso_m.group(2)), int(iso_m.group(3)))
        except ValueError:
            pass

    # 2. DD-MM-YYYY or DD/MM/YYYY
    dmy_m = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", normalized)
    if dmy_m:
        try:
            return date(int(dmy_m.group(3)), int(dmy_m.group(2)), int(dmy_m.group(1)))
        except ValueError:
            pass

    # 3. "april 14, 2024" / "apr 14 2024"
    mdy_m = re.search(
        r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b",
        normalized,
    )
    if mdy_m and mdy_m.group(1) in _DATE_MONTH_MAP:
        try:
            return date(int(mdy_m.group(3)), _DATE_MONTH_MAP[mdy_m.group(1)], int(mdy_m.group(2)))
        except ValueError:
            pass

    # 4. "14 april 2024"
    dmy_word_m = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+),?\s+(20\d{2})\b",
        normalized,
    )
    if dmy_word_m and dmy_word_m.group(2) in _DATE_MONTH_MAP:
        try:
            return date(int(dmy_word_m.group(3)), _DATE_MONTH_MAP[dmy_word_m.group(2)], int(dmy_word_m.group(1)))
        except ValueError:
            pass

    return None


def _clean_versus_fragment(text: str) -> str:
    """Collapse extra spaces and strip punctuation from team tokens."""
    return re.sub(r"\s+", " ", text).strip(" ?!.,")


def _extract_head_to_head_teams(normalized: str) -> Optional[Tuple[str, str]]:
    """
    Extract (team_one, team_two) from vs / versus / between / beaten questions.
    Strips dates, seasons, 'ipl', and result suffixes cleanly.
    """
    cleaned = normalized.strip(" ?!.")
    # Strip explicit dates, seasons, and 'ipl' tokens before isolating team strings.
    cleaned = re.sub(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]20\d{2}\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(?:on\s+)?(?:[a-z]+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\s+[a-z]+),?\s+20\d{2}\b",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"\b(?:in\s+)?(?:ipl\s+)?20\d{2}(?:/\d{2})?\b", " ", cleaned)
    cleaned = re.sub(r"\b(?:in\s+)?ipl\b", " ", cleaned)
    cleaned = re.sub(r"\bseason\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    leading_noise = (
        r"^(?:what\s+(?:is|are|was|were)\s+(?:the\s+)?|"
        r"show(?:\s+me)?\s+|tell\s+me(?:\s+about)?\s+|give\s+me\s+|get\s+|compare\s+|"
        r"who\s+won(?:\s+the)?\s+|how\s+many\s+times\s+(?:has|have)\s+|"
        r"head[- ]to[- ]head(?:\s+for|\s+of)?\s+|"
        r"(?:match\s+)?results?(?:\s+for|\s+of)?\s+|"
        r"scorecards?(?:\s+for|\s+of)?\s+|"
        r"fall\s+of\s+wickets(?:\s+for|\s+of)?\s+|"
        r"matches?(?:\s+for|\s+of)?\s+|the\s+)+"
    )
    trailing_noise = (
        r"\s+(?:head[- ]to[- ]head|match\s+results?|matches?|match|"
        r"results?|scorecards?|winners?|records?|stats|statistics|on|in|for).*$"
    )

    # Pattern 1: "<team1> vs/versus <team2>"
    vs_match = re.search(
        r"([a-z0-9 .'-]+?)\s+(?:vs\.?|versus)\s+([a-z0-9 .'-]+)",
        cleaned,
    )
    if vs_match:
        raw_one = re.sub(leading_noise, "", vs_match.group(1).strip())
        raw_two = re.sub(trailing_noise, "", vs_match.group(2).strip())
        raw_one = _clean_versus_fragment(raw_one)
        raw_two = _clean_versus_fragment(raw_two)
        if raw_one and raw_two:
            return raw_one, raw_two

    # Pattern 2: "<team1> beaten/defeated/won against <team2>"
    beaten_match = re.search(
        r"([a-z0-9 .'-]+?)\s+(?:beaten|beat|defeated|won\s+against)\s+([a-z0-9 .'-]+)",
        cleaned,
    )
    if beaten_match:
        raw_one = re.sub(leading_noise, "", beaten_match.group(1).strip())
        raw_two = re.sub(trailing_noise, "", beaten_match.group(2).strip())
        raw_one = _clean_versus_fragment(raw_one)
        raw_two = _clean_versus_fragment(raw_two)
        if raw_one and raw_two:
            return raw_one, raw_two

    # Pattern 3: "between <team1> and <team2>"
    between_match = re.search(
        r"\bbetween\s+([a-z0-9 .'-]+?)\s+and\s+([a-z0-9 .'-]+)",
        cleaned,
    )
    if between_match:
        raw_one = _clean_versus_fragment(between_match.group(1))
        raw_two = _clean_versus_fragment(
            re.sub(trailing_noise, "", between_match.group(2).strip())
        )
        if raw_one and raw_two:
            return raw_one, raw_two

    return None


def _extract_comparison_players(question: str) -> Optional[Tuple[str, str]]:
    """Extract two player names from 'Compare <p1> and/with/vs <p2> ...' queries."""
    cleaned = re.sub(r"[?!.]+$", "", question.strip())
    # Remove trailing explanation / season clauses before isolating the two player names.
    cleaned = re.sub(
        r"\s+and\s+(?:explain|analyze|describe|show\s+why).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s+(?:in|during|for|between|from)\s+(?:the\s+)?(?:ipl\s+)?20\d{2}(?:/\d{2})?\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    m = re.search(
        r"\bcompare\s+([A-Za-z .'-]{2,40}?)\s+(?:and|with|vs\.?|versus|to)\s+([A-Za-z .'-]{2,40})$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    p1 = re.sub(r"\s+(?:ipl|career|stats|statistics).*$", "", m.group(1).strip(), flags=re.IGNORECASE).strip()
    p2 = re.sub(r"\s+(?:ipl|career|stats|statistics).*$", "", m.group(2).strip(), flags=re.IGNORECASE).strip()
    cand1 = _clean_player_candidate(p1)
    cand2 = _clean_player_candidate(p2)
    if cand1 and cand2:
        return cand1, cand2
    return None


def _extract_comparison_player_across_seasons(question: str) -> Optional[str]:
    """
    Extract a single player name from multi-season comparison queries such as
    'Compare Kohli's performance in 2023 and 2026' or 'Compare Virat Kohli in 2020 vs 2024'.
    """
    cleaned = re.sub(r"[?!.]+$", "", question.strip())
    m = re.search(
        r"\bcompare\s+([A-Za-z .'-]{2,45}?)(?:'s)?\s+"
        r"(?:(?:ipl\s+)?(?:performance|stats|statistics|batting|bowling|form|record)\s+)?"
        r"(?:in|across|between|from|during)\s+(?:the\s+)?(?:ipl\s+)?20\d{2}",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    raw_name = re.sub(r"\s+(?:ipl|season|seasons)$", "", m.group(1).strip(), flags=re.IGNORECASE).strip()
    if _TEAM_KEYWORD_PATTERN.fullmatch(raw_name.lower()):
        return None
    return _clean_player_candidate(raw_name)


def _clean_player_candidate(raw: str) -> Optional[str]:
    candidate = re.sub(r"\s+", " ", raw).strip(" .,'?!-")
    candidate = re.sub(r"^(?:the|player)\s+", "", candidate, flags=re.IGNORECASE).strip()
    if not candidate or candidate.lower() in _GENERIC_PLAYER_REJECTS:
        return None
    if re.search(r"^(?:who|which|what|anyone|someone)\b", candidate, flags=re.IGNORECASE):
        return None
    if re.search(r"\d", candidate):
        return None
    if _TEAM_KEYWORD_PATTERN.fullmatch(candidate.lower()):
        return None
    return candidate


def _extract_player_name(question: str) -> Optional[str]:
    """Extract a player name from career, season-runs, matches-played, or season-wise questions."""
    # Strip trailing season suffix so "score in 2024" doesn't pollute player extraction.
    work = re.sub(
        r"\s+(?:in|during|for)\s+(?:the\s+)?(?:ipl\s+)?20\d{2}(?:/\d{2})?\b",
        "",
        question.strip(),
        flags=re.IGNORECASE,
    )
    work = re.sub(r"[?!.]+$", "", work).strip()

    # 1. "How many runs/matches/wickets did/has <Player> score/play/take"
    how_many = re.search(
        r"\bhow\s+many\s+(?:runs|sixes|fours|centuries|hundreds|fifties|wickets|matches)\s+"
        r"(?:did|has|have)\s+([A-Za-z .'-]{2,40}?)\s+(?:score|hit|take|taken|played|play|made|make)\b",
        work,
        flags=re.IGNORECASE,
    )
    if how_many:
        cand = _clean_player_candidate(how_many.group(1))
        if cand:
            return cand

    # Strip leading command phrases case-insensitively.
    cleaned = re.sub(
        r"^(?:show\s+me|show|tell\s+me\s+about|tell\s+me|give\s+me|get|display|what\s+(?:is|are))\s+",
        "",
        work,
        flags=re.IGNORECASE,
    )

    stat_suffix = (
        r"(?:ipl\s+)?(?:season[- ]wise|season\s+by\s+season|every\s+season|each\s+season|"
        r"batting|bowling|career|all[- ]time)?\s*"
        r"(?:batting|bowling|season[- ]wise)?\s*"
        r"(?:statistics|stats|career|record|records|performance|average|runs|wickets|matches)"
    )

    # 2. Possessive: "Virat Kohli's IPL statistics", "Jasprit Bumrah's bowling statistics"
    m = re.search(
        rf"([A-Za-z][A-Za-z .'-]{{1,40}}?)'s\s+{stat_suffix}",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m:
        cand = _clean_player_candidate(m.group(1))
        if cand:
            return cand

    # 3. Trigger preposition before name + stat suffix
    for trigger in ["for", "of", "about"]:
        m = re.search(
            rf"\b{trigger}\s+([A-Za-z][A-Za-z .'-]{{1,40}}?)(?:'s)?\s+{stat_suffix}",
            cleaned,
            flags=re.IGNORECASE,
        )
        if m:
            cand = _clean_player_candidate(m.group(1))
            if cand:
                return cand

    # 4. Direct name before stat keyword: "Virat Kohli batting statistics"
    m = re.search(
        rf"\b([A-Z][a-zA-Z .'-]{{1,40}}?)\s+{stat_suffix}",
        cleaned,
    )
    if m:
        cand = _clean_player_candidate(m.group(1))
        if cand:
            return cand

    # 5. Trailing "stats/performance for/of <Player>"
    m = re.search(
        r"(?:statistics|stats|career|record|records|performance)\s+(?:for|of)\s+([A-Za-z][A-Za-z .'-]{1,40})$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m:
        cand = _clean_player_candidate(m.group(1))
        if cand:
            return cand

    return None


def _extract_seasons(normalized: str) -> List[str]:
    """Extract all unique IPL season tokens in order of appearance, resolving aliases."""
    seasons: List[str] = []
    for match in re.finditer(r"\b(20\d{2}(?:/\d{2})?)\b", normalized):
        canon = normalize_season_token(match.group(1))
        if canon not in seasons:
            seasons.append(canon)
    return seasons


def _resolve_relative_season(
    season: Optional[str],
    cutoff_info: Dict[str, Any],
) -> Optional[str]:
    """Resolve explicit season or query Supabase for latest season on relative recency queries."""
    if season is not None:
        return season
    if cutoff_info.get("is_relative_recent") and not cutoff_info.get("is_all_time"):
        try:
            return get_latest_season()
        except Exception:
            return None
    return None


def extract_query_entities(question: str) -> Dict[str, Any]:
    """Extract normalized text, seasons, cutoff scope, date, match_id, limit, and teams."""
    normalized = re.sub(r"\s+", " ", question.lower().strip())

    match_date = _extract_date(normalized)
    seasons = _extract_seasons(normalized)
    season = seasons[0] if seasons else None
    has_since_range = bool(re.search(r"\bsince\s+20\d{2}(?:/\d{2})?\b", normalized))

    cutoff = classify_temporal_scope(
        normalized_question=normalized,
        seasons=seasons,
        match_date=match_date,
        has_since_range=has_since_range,
    )

    limit_match = re.search(r"\btop\s+(\d{1,3})\b", normalized)
    limit = int(limit_match.group(1)) if limit_match else 10
    limit = max(1, min(limit, 100))

    match_id_m = re.search(r"\bmatch\s*(?:id\s*)?(\d{5,8})\b", normalized)
    match_id = int(match_id_m.group(1)) if match_id_m else None

    team_matches = _TEAM_KEYWORD_PATTERN.findall(normalized)

    return {
        "normalized": normalized,
        "season": season,
        "seasons": seasons,
        "has_since_range": has_since_range,
        "cutoff": cutoff,
        "match_date": match_date,
        "match_id": match_id,
        "limit": limit,
        "has_explicit_limit": limit_match is not None,
        "teams": team_matches,
    }


def route_question(question: str) -> str:
    """Route natural-language IPL questions across SQL, direct within-cutoff Gemini, and pgvector RAG."""

    if not question or not question.strip():
        return "Please enter a cricket question."

    entities = extract_query_entities(question)
    normalized = entities["normalized"]
    season = entities["season"]
    seasons = entities["seasons"]
    cutoff = entities["cutoff"]
    match_date = entities["match_date"]
    match_id = entities["match_id"]
    limit = entities["limit"]
    team_matches = entities["teams"]

    def eff_season() -> Optional[str]:
        return _resolve_relative_season(season, cutoff)

    # ------------------------------------------------------------------
    # 1. Explicit match ID queries (wickets / scorecard / POTM / last over / summary)
    # ------------------------------------------------------------------
    if match_id is not None:
        if any(t in normalized for t in [
            "fall of wickets", "wicket fell", "wickets fell",
            "wicket details", "dismissals",
        ]):
            return answer_wickets_question(match_id)

        if any(t in normalized for t in [
            "player of the match", "man of the match", "potm", "motm",
        ]):
            return answer_match_awards_question(match_id=match_id)

        if any(t in normalized for t in ["last over", "final over", "20th over"]):
            return answer_last_over_question(match_id)

        if any(t in normalized for t in [
            "scorecard", "score card", "batting figures", "bowling figures",
            "innings details", "full score", "innings-wise", "innings wise",
        ]):
            return answer_scorecard_question(match_id)

        return answer_match_question(match_id, question)

    # ------------------------------------------------------------------
    # 2. First IPL match
    # ------------------------------------------------------------------
    if any(pattern in normalized for pattern in FIRST_MATCH_PATTERNS):
        first_id = get_first_match_id()
        if first_id is None:
            return "No IPL match records are currently available."
        return answer_match_question(first_id, question)

    # ------------------------------------------------------------------
    # 3. Advanced cricket records & phase / extras queries (Section 2G)
    # ------------------------------------------------------------------
    if any(t in normalized for t in [
        "run chase", "successful chase", "highest chase", "biggest chase",
    ]):
        return answer_highest_chases_question(season=eff_season(), limit=limit)

    if any(t in normalized for t in [
        "biggest win", "biggest victory", "largest win",
        "largest victory", "largest margin",
    ]):
        by = "wickets" if "wicket" in normalized else "runs"
        return answer_biggest_victories_question(by=by, season=eff_season(), limit=limit)

    if any(t in normalized for t in [
        "highest team total", "highest total", "highest team score",
    ]):
        return answer_team_totals_question(highest=True, season=eff_season(), limit=limit)

    if any(t in normalized for t in [
        "lowest team total", "lowest total", "lowest team score",
    ]):
        return answer_team_totals_question(highest=False, season=eff_season(), limit=limit)

    if any(t in normalized for t in [
        "most sixes in an innings", "sixes in an innings", "most sixes in a match",
    ]):
        return answer_most_sixes_innings_question(season=eff_season(), limit=limit)

    if any(t in normalized for t in [
        "powerplay", "power play", "middle over", "middle-over", "death over", "death-over",
    ]):
        if "powerplay" in normalized or "power play" in normalized:
            phase = "powerplay"
        elif "middle" in normalized:
            phase = "middle"
        else:
            phase = "death"

        stat_type = (
            "bowling"
            if any(w in normalized for w in ["bowl", "wicket", "economy"])
            else "batting"
        )
        return answer_phase_stats_question(
            phase=phase,
            stat_type=stat_type,
            season=eff_season(),
            limit=limit,
        )

    if any(t in normalized for t in [
        "extras", "dismissal types", "types of dismissals", "dismissal statistics",
        "dismissals breakdown", "how batters get out",
    ]):
        return answer_extras_dismissals_question(season=eff_season())

    # ------------------------------------------------------------------
    # 4. Player of the Match (without match ID: season final or all-time)
    # ------------------------------------------------------------------
    if any(t in normalized for t in ["player of the match", "man of the match", "potm", "motm"]):
        resolved = eff_season()
        return answer_match_awards_question(
            season=resolved,
            final_only=("final" in normalized and resolved is not None),
            limit=limit,
        )

    # ------------------------------------------------------------------
    # 5. Match by Date & Team-vs-Team / Head-to-Head (Sections 2E & 2F)
    # ------------------------------------------------------------------
    is_versus_trigger = bool(
        re.search(r"\b(?:vs\.?|versus)\b|head[- ]to[- ]head", normalized)
        or re.search(r"\b(?:beaten|beat|defeated|won\s+against)\b", normalized)
        or ("between" in normalized and len(team_matches) >= 1)
    )

    if match_date is not None:
        extracted_teams = _extract_head_to_head_teams(normalized) if is_versus_trigger else None
        t1 = extracted_teams[0] if extracted_teams else (team_matches[0] if len(team_matches) >= 1 else None)
        t2 = extracted_teams[1] if extracted_teams else (team_matches[1] if len(team_matches) >= 2 else None)
        return answer_match_by_date_question(
            match_date=match_date,
            team_one=t1,
            team_two=t2,
            wants_scorecard="scorecard" in normalized or "innings" in normalized,
            wants_wickets="fall of wickets" in normalized or "wickets" in normalized,
            wants_last_over="last over" in normalized or "final over" in normalized,
            wants_potm="player of the match" in normalized or "man of the match" in normalized,
        )

    if is_versus_trigger:
        teams = _extract_head_to_head_teams(normalized)
        if teams:
            resolved = eff_season()
            if resolved is not None and not cutoff["is_all_time"]:
                return answer_team_versus_matches_question(teams[0], teams[1], season=resolved)
            return answer_head_to_head_question(teams[0], teams[1])

    # Ambiguous match-specific requests without match ID or date
    if any(t in normalized for t in [
        "show the scorecard", "show scorecard", "fall of wickets",
        "last over", "innings-wise scores", "innings wise scores",
    ]) and match_id is None and match_date is None:
        return (
            "Please specify a match ID or date and teams to retrieve match details "
            "(for example: 'Show scorecard for match 335982' or "
            "'What was the result of the CSK vs MI match on 2024-04-14?')."
        )

    # ------------------------------------------------------------------
    # 6. IPL Season Winner (Section 2F + relative 'latest/current' resolution)
    # ------------------------------------------------------------------
    winner_terms = [
        "winner", "winners", "champion", "champions",
        "who won", "which team won",
    ]
    is_season_winner_question = (
        (season is not None or cutoff["is_relative_recent"])
        and any(term in normalized for term in winner_terms)
        and ("ipl" in normalized or "season" in normalized)
        and not team_matches
        and not is_versus_trigger
    )
    if is_season_winner_question:
        resolved = eff_season()
        if resolved is None:
            return "No IPL season winner record is currently available."
        return answer_season_winner_question(resolved)

    # ------------------------------------------------------------------
    # 7. Comparisons: Two Players (SQL vs Hybrid) | Single-Player Multi-Season | Season/Team
    # ------------------------------------------------------------------
    if "compare" in normalized:
        wants_hybrid_explanation = any(
            t in normalized for t in ["explain", "difference", "why", "analyze", "describe", "how"]
        )
        comp_players = _extract_comparison_players(question)
        if comp_players:
            if len(seasons) >= 2:
                return answer_cross_boundary_question(
                    question,
                    seasons=seasons,
                    team_identifiers=team_matches,
                    cutoff_info=cutoff,
                )
            resolved = eff_season()
            if wants_hybrid_explanation:
                return answer_hybrid_player_comparison_question(
                    question,
                    comp_players[0],
                    comp_players[1],
                    season=resolved,
                )
            if resolved is not None:
                return answer_player_comparison_question(
                    comp_players[0],
                    comp_players[1],
                    season=resolved,
                )
            return answer_player_comparison_question(comp_players[0], comp_players[1])

        single_player = _extract_comparison_player_across_seasons(question)
        if single_player and len(seasons) >= 2:
            return answer_player_multi_season_comparison_question(
                question,
                single_player,
                seasons,
                cutoff_info=cutoff,
            )

        if len(seasons) >= 2 or cutoff["scope"] in {"cross_cutoff", "post_cutoff"} or team_matches:
            if cutoff["scope"] == "within_cutoff" and not wants_hybrid_explanation and team_matches:
                # Historical season/team narrative comparison within configured cutoff
                return answer_historical_llm_question(
                    question,
                    seasons=seasons,
                    team_identifier=team_matches[0] if team_matches else None,
                )
            if cutoff["scope"] == "within_cutoff" and not team_matches:
                return answer_historical_llm_question(question, seasons=seasons)
            return answer_cross_boundary_question(
                question,
                seasons=seasons,
                team_identifiers=team_matches,
                cutoff_info=cutoff,
            )

        return "Please specify two players or seasons to compare (for example: 'Compare Kohli and Rohit Sharma' or 'Compare IPL 2016 and IPL 2026')."

    # ------------------------------------------------------------------
    # 8. Shared Intent & Boundary Signals
    # ------------------------------------------------------------------
    if any(t in normalized for t in [
        "which team scored the most runs", "team with most runs",
        "teams by runs", "most runs by a team",
    ]):
        return answer_team_runs_leaderboard_question(season=eff_season(), limit=limit)

    if any(t in normalized for t in [
        "most ipl titles", "most titles", "most trophies",
        "most championships", "which team has won the most",
    ]) and not team_matches:
        return answer_most_titles_question()

    has_leaderboard_phrase = (
        entities["has_explicit_limit"]
        or any(term in normalized for term in _LEADERBOARD_GUARD_TERMS)
        or "run scorer" in normalized
        or "wicket taker" in normalized
    )

    is_rule_question = any(t in normalized for t in [
        "dls", "duckworth", "impact player", "rule", "rules", "playing conditions",
    ])
    is_narrative_question = any(t in normalized for t in [
        "explain", "campaign", "history", "story", "journey",
        "summary", "summarize", "recap", "why did", "why was",
        "how did", "what happened", "tell me about",
    ])
    wants_explicit_stats = any(t in normalized for t in [
        "statistics", "stats", "using match statistics", "using statistics",
        "record", "records", "win percentage", "win rate",
        "wins", "losses", "titles", "trophies", "championships",
        "how many matches", "how many wins", "batting average", "bowling economy",
    ])

    # ------------------------------------------------------------------
    # 8a. Rules & Hybrid Team Statistics + Narrative
    # ------------------------------------------------------------------
    if is_rule_question and not has_leaderboard_phrase:
        return answer_rag_narrative_question(question, season=eff_season())

    if (
        team_matches
        and not has_leaderboard_phrase
        and wants_explicit_stats
        and any(t in normalized for t in ["explain", "why", "analyze", "using match statistics", "using statistics"])
    ):
        return answer_hybrid_team_question(question, team_matches[0], season=eff_season())

    # ------------------------------------------------------------------
    # 8b. Knowledge-Cutoff-Aware Narrative / History / Overview Routing
    # ------------------------------------------------------------------
    if (is_narrative_question and not wants_explicit_stats and not has_leaderboard_phrase) or (
        len(seasons) >= 2 and not has_leaderboard_phrase and cutoff["scope"] == "cross_cutoff"
    ):
        if cutoff["scope"] == "within_cutoff":
            return answer_historical_llm_question(
                question,
                seasons=seasons,
                team_identifier=team_matches[0] if team_matches else None,
            )

        if cutoff["scope"] == "cross_cutoff":
            return answer_cross_boundary_question(
                question,
                seasons=seasons,
                team_identifiers=team_matches,
                cutoff_info=cutoff,
            )

        resolved = eff_season()
        if cutoff["is_relative_recent"] and any(
            t in normalized for t in ["what happened", "summary", "summarize", "recap", "overview", "season"]
        ):
            return answer_post_cutoff_overview_question(question, season=resolved)

        return answer_rag_narrative_question(question, season=resolved)

    # ------------------------------------------------------------------
    # 8c. Pure Team Statistics (SQL)
    # ------------------------------------------------------------------
    if team_matches and not has_leaderboard_phrase:
        team_stat_indicators = [
            "statistics", "stats", "record", "records", "performance",
            "win", "wins", "won", "lose", "lost", "loss", "losses",
            "matches", "batting", "bowling",
            "titles", "trophies", "championship", "championships",
            "win percentage", "win rate", "ipl",
        ]
        if any(term in normalized for term in team_stat_indicators):
            resolved = eff_season()
            if resolved is not None and not cutoff["is_all_time"]:
                return answer_team_question(team_matches[0], season=resolved)
            return answer_team_question(team_matches[0])

    # ------------------------------------------------------------------
    # 9. Individual Player Statistics & Season Breakdown (Sections 2A & 2C)
    # ------------------------------------------------------------------
    if not has_leaderboard_phrase and not team_matches:
        is_season_wise = any(t in normalized for t in [
            "season-wise", "season wise", "season by season",
            "every season", "each season", "all seasons",
        ])
        player_indicators = [
            "statistics", "stats", "career", "record", "records", "performance",
            "how many runs", "how many matches", "how many wickets",
            "how many sixes", "how many fours", "how many centuries",
            "batting average", "bowling average", "batting stats", "bowling stats",
        ]
        if is_season_wise or any(term in normalized for term in player_indicators):
            player_name = _extract_player_name(question)
            if player_name:
                if is_season_wise:
                    return answer_player_season_breakdown_question(player_name)
                resolved = eff_season()
                if resolved is not None and not cutoff["is_all_time"]:
                    return answer_player_question(player_name, season=resolved)
                return answer_player_question(player_name)

    # ------------------------------------------------------------------
    # 10. Bowling Leaderboards (Section 2B)
    # ------------------------------------------------------------------
    if any(term in normalized for term in [
        "best bowling figures", "best bowling performance", "best bowling spell",
    ]):
        return answer_leaderboard_question(
            category="wickets",
            question_type="best_bowling",
            season=eff_season(),
            limit=limit,
        )

    if any(term in normalized for term in [
        "five-wicket", "five wicket", "5-wicket", "5 wicket", "fifer", "five-fer",
    ]):
        return answer_leaderboard_question(
            category="five_wickets",
            question_type="bowling",
            season=eff_season(),
            limit=limit,
        )

    bowling_question = any(term in normalized for term in [
        "bowler", "bowlers", "bowling", "wickets", "wicket taker",
        "economy", "economical", "purple cap",
    ])
    if bowling_question:
        if "economy" in normalized or "economical" in normalized:
            category = "economy"
        elif "strike rate" in normalized:
            category = "strike_rate"
        elif "average" in normalized:
            category = "average"
        else:
            category = "wickets"

        return answer_leaderboard_question(
            category=category,
            question_type="bowling",
            season=eff_season(),
            limit=limit,
        )

    # ------------------------------------------------------------------
    # 11. Batting Leaderboards (Section 2A)
    # ------------------------------------------------------------------
    if any(term in normalized for term in [
        "highest individual score", "highest individual scores",
        "highest score", "high score", "individual score", "individual scores",
    ]):
        return answer_highest_individual_scores_question(season=eff_season(), limit=limit)

    if "six" in normalized and "four" in normalized:
        return answer_boundaries_combined_question(season=eff_season(), limit=limit)

    batting_question = any(term in normalized for term in [
        "run scorer", "runs", "batter", "batsman", "batsmen", "batting",
        "orange cap", "six", "four", "strike rate", "average",
        "centuries", "century", "hundreds", "fifties", "half-centuries", "half centuries",
    ])
    if batting_question:
        if any(t in normalized for t in ["centuries", "century", "hundreds", "100s"]):
            category = "centuries"
        elif any(t in normalized for t in ["fifties", "half-centuries", "half centuries", "50s"]):
            category = "fifties"
        elif "six" in normalized:
            category = "sixes"
        elif "four" in normalized:
            category = "fours"
        elif "strike rate" in normalized:
            category = "strike_rate"
        elif "average" in normalized:
            category = "average"
        else:
            category = "runs"

        return answer_leaderboard_question(
            category=category,
            question_type="batting",
            season=eff_season(),
            limit=limit,
        )

    # ------------------------------------------------------------------
    # 12. Open-ended Fallback (Cutoff-Aware)
    # ------------------------------------------------------------------
    if len(normalized.split()) >= 3:
        if cutoff["scope"] == "within_cutoff":
            return answer_historical_llm_question(question, seasons=seasons)
        if cutoff["scope"] == "cross_cutoff":
            return answer_cross_boundary_question(
                question,
                seasons=seasons,
                team_identifiers=team_matches,
                cutoff_info=cutoff,
            )
        return answer_rag_narrative_question(question, season=eff_season())

    return (
        "I can answer IPL questions across batting/bowling leaderboards, player stats "
        "and comparisons, team stats and titles, head-to-head and season match results, "
        "scorecards, fall of wickets, Player of the Match awards, cricket rules, and "
        "season/match narratives."
    )
