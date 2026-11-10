"""
Application-defined knowledge cutoff configuration and temporal scope classifier.

IMPORTANT:
`GEMINI_KNOWLEDGE_CUTOFF_DATE` and `GEMINI_KNOWLEDGE_CUTOFF_SEASON` define an
application-level conservative routing boundary so CricketGPT knows when a user
question can rely directly on Gemini's parametric historical knowledge vs when it
MUST retrieve verified post-cutoff data from Supabase SQL and pgvector RAG.
These settings are NOT a claim about Google Gemini's exact model training cutoff.
"""

from datetime import date
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_KNOWLEDGE_CUTOFF_DATE = "2024-03-01"
DEFAULT_KNOWLEDGE_CUTOFF_SEASON = "2023"

SEASON_ALIASES: Dict[str, str] = {
    "2008": "2007/08",
    "2010": "2009/10",
    "2020": "2020/21",
}

_CANONICAL_TO_YEAR: Dict[str, int] = {
    "2007/08": 2008,
    "2009/10": 2010,
    "2020/21": 2020,
}

_RELATIVE_RECENT_RE = re.compile(
    r"\b(?:latest|current\s+season|this\s+season|this\s+year|present\s+season|"
    r"most\s+recent|recent|recently|last\s+season|ongoing|so\s+far|right\s+now|today)\b",
    re.IGNORECASE,
)

_ALL_TIME_RE = re.compile(
    r"\b(?:all[- ]time|all\s+seasons|every\s+season|overall|throughout\s+ipl\s+history|ever)\b",
    re.IGNORECASE,
)

_SINCE_YEAR_RE = re.compile(r"\bsince\s+(20\d{2}(?:/\d{2})?)\b", re.IGNORECASE)
_RANGE_YEARS_RE = re.compile(
    r"\b(?:from\s+)?(20\d{2}(?:/\d{2})?)\s+(?:to|through|until|-)\s+(20\d{2}(?:/\d{2})?)\b",
    re.IGNORECASE,
)


def normalize_season_token(raw_season: str) -> str:
    """Normalize year tokens such as '2008' -> '2007/08', '2020' -> '2020/21'."""
    token = raw_season.strip()
    return SEASON_ALIASES.get(token, token)


def season_to_year(season_str: str) -> int:
    """
    Convert an IPL season identifier ('2007/08', '2020/21', '2024') to its
    chronological tournament calendar year (e.g., 2008, 2020, 2024).
    """
    cleaned = str(season_str).strip()
    if cleaned in _CANONICAL_TO_YEAR:
        return _CANONICAL_TO_YEAR[cleaned]
    if "/" in cleaned:
        prefix = cleaned.split("/", 1)[0]
        if prefix.isdigit():
            return int(prefix)
    match = re.search(r"(20\d{2})", cleaned)
    if match:
        return int(match.group(1))
    raise ValueError(f"Cannot parse IPL season year from '{season_str}'.")


def get_knowledge_cutoff_date() -> date:
    """Return configured conservative routing cutoff date (default 2024-03-01)."""
    raw = os.getenv("GEMINI_KNOWLEDGE_CUTOFF_DATE", DEFAULT_KNOWLEDGE_CUTOFF_DATE).strip()
    if not raw:
        return date.fromisoformat(DEFAULT_KNOWLEDGE_CUTOFF_DATE)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        logger.warning(
            "Invalid GEMINI_KNOWLEDGE_CUTOFF_DATE '%s'; falling back to %s.",
            raw,
            DEFAULT_KNOWLEDGE_CUTOFF_DATE,
        )
        return date.fromisoformat(DEFAULT_KNOWLEDGE_CUTOFF_DATE)


def get_knowledge_cutoff_season() -> str:
    """Return configured conservative routing cutoff season string (default '2023')."""
    raw = os.getenv("GEMINI_KNOWLEDGE_CUTOFF_SEASON", DEFAULT_KNOWLEDGE_CUTOFF_SEASON).strip()
    return raw or DEFAULT_KNOWLEDGE_CUTOFF_SEASON


def get_knowledge_cutoff_season_year() -> int:
    """Return integer year of configured GEMINI_KNOWLEDGE_CUTOFF_SEASON."""
    raw = get_knowledge_cutoff_season()
    try:
        return season_to_year(raw)
    except ValueError:
        logger.warning(
            "Invalid GEMINI_KNOWLEDGE_CUTOFF_SEASON '%s'; falling back to %s.",
            raw,
            DEFAULT_KNOWLEDGE_CUTOFF_SEASON,
        )
        return season_to_year(DEFAULT_KNOWLEDGE_CUTOFF_SEASON)


def classify_temporal_scope(
    normalized_question: str,
    seasons: List[str],
    match_date: Optional[date] = None,
    has_since_range: bool = False,
) -> Dict[str, Any]:
    """
    Classify a normalized question against the application's configured knowledge boundary:
    - 'within_cutoff': All referenced seasons/dates fall at or before the configured boundary.
    - 'post_cutoff': Any referenced season/date exceeds the boundary or asks for latest/recent data.
    - 'cross_cutoff': Spans both within-boundary and post-boundary periods (e.g. 2016 vs 2026,
                      'since 2020', or 'all-time' when current season > cutoff).
    - 'ambiguous': No explicit temporal cue; treated conservatively via Supabase when unsure.
    """
    cutoff_date = get_knowledge_cutoff_date()
    cutoff_season_str = get_knowledge_cutoff_season()
    cutoff_year = get_knowledge_cutoff_season_year()

    is_relative_recent = bool(_RELATIVE_RECENT_RE.search(normalized_question))
    is_all_time = bool(_ALL_TIME_RE.search(normalized_question))

    within_seasons: List[str] = []
    post_seasons: List[str] = []

    for s in seasons:
        try:
            year = season_to_year(s)
        except ValueError:
            continue
        if year <= cutoff_year:
            within_seasons.append(s)
        else:
            post_seasons.append(s)

    date_is_within = False
    date_is_post = False
    if match_date is not None:
        if match_date <= cutoff_date:
            date_is_within = True
        else:
            date_is_post = True

    has_within = bool(within_seasons) or date_is_within
    has_beyond = bool(post_seasons) or date_is_post or is_relative_recent

    # Phrases like "since 2020" or "all-time" span from historical years into post-cutoff territory.
    if has_since_range or (is_all_time and not has_beyond and not seasons):
        if has_since_range and has_within:
            has_beyond = True
        elif is_all_time:
            has_within = True
            has_beyond = True

    if has_within and has_beyond:
        scope = "cross_cutoff"
    elif has_beyond:
        scope = "post_cutoff"
    elif has_within:
        scope = "within_cutoff"
    else:
        scope = "ambiguous"

    return {
        "scope": scope,
        "cutoff_date": cutoff_date.isoformat(),
        "cutoff_season": cutoff_season_str,
        "cutoff_season_year": cutoff_year,
        "within_seasons": within_seasons,
        "post_seasons": post_seasons,
        "is_relative_recent": is_relative_recent,
        "is_all_time": is_all_time,
    }

