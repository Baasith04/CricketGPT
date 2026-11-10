import re

from app.ai.answer_service import (
    answer_head_to_head_question,
    answer_leaderboard_question,
    answer_match_question,
    answer_player_question,
    answer_scorecard_question,
    answer_season_winner_question,
    answer_team_question,
    answer_team_versus_matches_question,
    answer_wickets_question,
)
from app.services.matches.match_service import get_first_match_id


FIRST_MATCH_PATTERNS = [
    "first match of ipl",
    "1st match of ipl",
    "opening match of ipl",
    "first ipl match",
    "inaugural ipl match",
]

# Known IPL team keywords for intent detection (lowercase, matched on word boundaries).
IPL_TEAM_KEYWORDS = [
    "mumbai indians",
    "chennai super kings",
    "royal challengers bengaluru",
    "royal challengers bangalore",
    "royal challengers",
    "kolkata knight riders",
    "sunrisers hyderabad",
    "delhi capitals",
    "delhi daredevils",
    "rajasthan royals",
    "kings xi punjab",
    "punjab kings",
    "deccan chargers",
    "kochi tuskers kerala",
    "kochi tuskers",
    "pune warriors",
    "rising pune supergiants",
    "rising pune supergiant",
    "gujarat titans",
    "gujarat lions",
    "lucknow super giants",
    "mi",
    "csk",
    "rcb",
    "kkr",
    "srh",
    "dc",
    "rr",
    "kxip",
    "pbks",
    "gt",
    "lsg",
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
    "orange cap",
    "purple cap",
    "best economy",
    "most economical",
    "best strike rate",
    "best average",
    "most sixes",
    "most fours",
]

_GENERIC_PLAYER_REJECTS = {
    "ipl",
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
    "all",
    "overall",
}


def _clean_versus_fragment(text: str) -> str:
    """Collapse extra spaces and punctuation around extracted team fragments."""
    return re.sub(r"\s+", " ", text).strip(" ?!.,")


def _extract_head_to_head_teams(normalized: str):
    """
    Extract (team_one, team_two) from vs / versus / between questions.

    Season tokens (e.g. '2024', '2007/08', 'in 2024', 'ipl') and trailing
    result/record suffixes are stripped separately so team identifiers stay clean.
    """
    cleaned = normalized.strip(" ?!.")
    # Strip season and 'ipl' markers anywhere in the query (already extracted as `season`).
    cleaned = re.sub(r"\b(?:in\s+)?(?:ipl\s+)?20\d{2}(?:/\d{2})?\b", " ", cleaned)
    cleaned = re.sub(r"\b(?:in\s+)?ipl\b", " ", cleaned)
    cleaned = re.sub(r"\bseason\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    leading_noise = (
        r"^(?:show(?:\s+me)?|tell\s+me|what\s+(?:is|are|was|were)|"
        r"who\s+won(?:\s+the)?|give\s+me|get|compare|"
        r"head[- ]to[- ]head(?:\s+for|\s+of)?|"
        r"match\s+results?(?:\s+for|\s+of)?|"
        r"matches?(?:\s+for|\s+of)?|"
        r"results?(?:\s+for|\s+of)?)\s+"
    )
    trailing_noise = (
        r"\s+(?:head[- ]to[- ]head|match\s+results?|matches?|"
        r"results?|scorecards?|winners?|records?|stats|statistics|in|for).*$"
    )

    # Pattern 1: "<team1> vs/versus <team2>"
    vs_match = re.search(
        r"([a-z0-9 .'-]+?)\s+(?:vs\.?|versus)\s+([a-z0-9 .'-]+)",
        cleaned,
    )
    if vs_match:
        raw_one = re.sub(leading_noise, "", vs_match.group(1).strip())
        raw_one = re.sub(leading_noise, "", raw_one)
        raw_two = re.sub(trailing_noise, "", vs_match.group(2).strip())
        raw_one = _clean_versus_fragment(raw_one)
        raw_two = _clean_versus_fragment(raw_two)
        if raw_one and raw_two:
            return raw_one, raw_two

    # Pattern 2: "between <team1> and <team2>"
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


def _extract_player_name(question: str):
    """Extract a player name from an individual player statistics question."""
    stat_suffix = (
        r"(?:batting|bowling|career|ipl|all[- ]time)?\s*"
        r"(?:batting|bowling)?\s*"
        r"(?:statistics|stats|career|record|average)"
    )

    # Strip leading command phrases case-insensitively before extracting name.
    cleaned = re.sub(
        r"^(?:show\s+me|show|tell\s+me\s+about|tell\s+me|give\s+me|get|display|what\s+(?:is|are))\s+",
        "",
        question.strip(),
        flags=re.IGNORECASE,
    )

    for trigger in ["for", "of", "about"]:
        m = re.search(
            rf"\b{trigger}\s+([A-Z][a-zA-Z .'-]{{1,40}}?)(?:'s)?\s+{stat_suffix}",
            cleaned,
            flags=re.IGNORECASE,
        )
        if m:
            candidate = m.group(1).strip(" .'")
            if candidate.lower() not in _GENERIC_PLAYER_REJECTS:
                return candidate

    # Possessive pattern: "MS Dhoni's career stats"
    m = re.search(
        rf"([A-Z][a-zA-Z .'-]{{1,40}}?)'s\s+{stat_suffix}",
        cleaned,
    )
    if m:
        candidate = m.group(1).strip(" .'")
        if candidate.lower() not in _GENERIC_PLAYER_REJECTS:
            return candidate

    # Direct capitalized name before stat keyword: "Jasprit Bumrah bowling statistics"
    m = re.search(
        rf"\b([A-Z][a-zA-Z .'-]{{1,40}}?)\s+{stat_suffix}",
        cleaned,
    )
    if m:
        candidate = m.group(1).strip(" .'")
        if candidate.lower() not in _GENERIC_PLAYER_REJECTS:
            return candidate

    # Trailing "stats for <Player>" pattern
    m = re.search(
        r"(?:statistics|stats|career|record)\s+(?:for|of)\s+([A-Z][a-zA-Z .'-]{1,40})$",
        cleaned.rstrip("?!."),
    )
    if m:
        candidate = m.group(1).strip(" .'")
        if candidate.lower() not in _GENERIC_PLAYER_REJECTS:
            return candidate

    return None


def route_question(question: str) -> str:
    """Route supported IPL questions to their SQL services."""

    if not question or not question.strip():
        return "Please enter a cricket question."

    normalized = question.lower().strip()

    # Extract IPL season.
    season_match = re.search(
        r"\b(20\d{2}(?:/\d{2})?)\b",
        normalized,
    )
    season = season_match.group(1) if season_match else None

    # Map common year references to database season labels.
    season_aliases = {
        "2008": "2007/08",
        "2010": "2009/10",
        "2020": "2020/21",
    }

    if season:
        season = season_aliases.get(season, season)

    # Extract requested leaderboard limit.
    limit_match = re.search(r"\btop\s+(\d{1,2})\b", normalized)
    limit = int(limit_match.group(1)) if limit_match else 10
    limit = max(1, min(limit, 100))

    # Intent A — IPL season winner questions.
    winner_terms = [
        "winner",
        "winners",
        "champion",
        "champions",
        "who won",
        "which team won",
    ]

    is_season_winner_question = (
        season is not None
        and any(term in normalized for term in winner_terms)
        and "ipl" in normalized
        and not re.search(r"\b(?:vs\.?|versus)\b|head[- ]to[- ]head", normalized)
    )

    if is_season_winner_question:
        return answer_season_winner_question(season)

    # Intent B — First IPL match.
    if any(pattern in normalized for pattern in FIRST_MATCH_PATTERNS):
        match_id = get_first_match_id()

        if match_id is None:
            return "No IPL match records are currently available."

        return answer_match_question(match_id, question)

    # Intent C — Specific match ID (wickets / scorecard / result).
    match = re.search(
        r"\bmatch\s*(?:id\s*)?(\d{5,8})\b",
        normalized,
    )

    if match:
        match_id = int(match.group(1))

        wickets_patterns = [
            "fall of wickets",
            "wicket fell",
            "wickets fell",
            "wicket details",
            "dismissals",
        ]

        if any(term in normalized for term in wickets_patterns):
            return answer_wickets_question(match_id)

        scorecard_patterns = [
            "scorecard",
            "score card",
            "batting figures",
            "bowling figures",
            "innings details",
            "full score",
        ]

        if any(term in normalized for term in scorecard_patterns):
            return answer_scorecard_question(match_id)

        return answer_match_question(match_id, question)

    # Intent D — Best bowling figures.
    if any(term in normalized for term in [
        "best bowling figures",
        "best bowling performance",
        "best bowling spell",
    ]):
        return answer_leaderboard_question(
            category="wickets",
            question_type="best_bowling",
            season=season,
            limit=limit,
        )

    # Intent I — Team-versus-team queries (season match results vs all-time head-to-head).
    is_h2h_trigger = bool(
        re.search(r"\b(?:vs\.?|versus)\b|head[- ]to[- ]head", normalized)
        or ("between" in normalized and _TEAM_KEYWORD_PATTERN.search(normalized))
    )

    if is_h2h_trigger:
        teams = _extract_head_to_head_teams(normalized)
        if teams:
            if season is not None:
                return answer_team_versus_matches_question(
                    teams[0],
                    teams[1],
                    season=season,
                )
            return answer_head_to_head_question(teams[0], teams[1])

    has_leaderboard_phrase = (
        limit_match is not None
        or any(term in normalized for term in _LEADERBOARD_GUARD_TERMS)
    )

    # Intent H — Individual team statistics (checked before leaderboards and player stats).
    team_match = _TEAM_KEYWORD_PATTERN.search(normalized)
    team_stat_terms = [
        "statistics",
        "stats",
        "record",
        "performance",
        "how many titles",
        "how many trophies",
        "how many championships",
        "championship",
        "trophies",
        "titles",
        "win percentage",
        "win rate",
    ]
    is_team_question = (
        team_match is not None
        and not has_leaderboard_phrase
        and (
            any(term in normalized for term in team_stat_terms)
            or "ipl" in normalized
        )
    )

    if is_team_question:
        return answer_team_question(team_match.group(1))

    # Intent G — Individual player statistics (checked before generic bowling/batting leaderboards).
    player_stat_terms = [
        "statistics",
        "stats",
        "career",
        "record",
        "batting average",
        "bowling average",
        "batting stats",
        "bowling stats",
        "runs scored",
        "wickets taken",
    ]
    is_player_question = (
        not has_leaderboard_phrase
        and team_match is None
        and any(term in normalized for term in player_stat_terms)
    )

    if is_player_question:
        player_name = _extract_player_name(question)
        if player_name:
            return answer_player_question(player_name)

    # Intent E — Bowling leaderboard.
    bowling_question = any(term in normalized for term in [
        "bowler",
        "bowlers",
        "bowling",
        "wickets",
        "wicket taker",
        "economy",
        "economical",
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
            season=season,
            limit=limit,
        )

    # Intent F — Batting leaderboard.
    batting_question = any(term in normalized for term in [
        "run scorer",
        "runs",
        "batter",
        "batsman",
        "batsmen",
        "batting",
        "orange cap",
        "six",
        "four",
        "strike rate",
        "highest score",
        "high score",
        "individual score",
    ])

    if batting_question:
        if any(term in normalized for term in [
            "highest score",
            "high score",
            "individual score",
        ]):
            category = "highest_score"
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
            season=season,
            limit=limit,
        )

    return (
        "I can answer IPL questions about season winners, match results, "
        "scorecards, batting/bowling leaderboards, player statistics, "
        "team statistics, and head-to-head records. "
        "Try asking: 'Show Virat Kohli's batting stats', "
        "'Mumbai Indians statistics', 'CSK vs MI head-to-head', "
        "'Who won IPL 2023', or 'Most wickets in IPL'."
    )
