"""
ipl_guard.py — IPL Domain Validation and Relevance Guard for CricketGPT.

Restricts CricketGPT to answering IPL-related questions only:
- Allowed:
  * IPL teams, franchises and players in IPL context
  * IPL seasons, matches, points tables and standings
  * IPL statistics, records and awards (Orange Cap, Purple Cap, etc.)
  * Auctions, squads, player prices and retention
  * IPL strategies, captaincy and team comparisons
  * IPL rules, playoffs and tournament history
  * IPL-related follow-up questions
- Rejected:
  * International cricket unrelated to IPL (Tests, ODIs, T20 World Cups, etc.)
  * Other cricket leagues (BBL, PSL, CPL, The Hundred, SA20, etc.)
  * Football, other sports and unrelated general knowledge
  * Programming, mathematics and unrelated topics

Exact rejection message:
"I'm CricketGPT, and I currently answer only IPL-related questions. Please ask me something about IPL!"
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

IPL_RESTRICTION_MESSAGE = (
    "I'm CricketGPT, and I currently answer only IPL-related questions. "
    "Please ask me something about IPL!"
)

# ---------------------------------------------------------------------------
# 1. Non-IPL Rejection Patterns (Fast Rule-Based Reject)
# ---------------------------------------------------------------------------

# International cricket formats and tournaments outside IPL
NON_IPL_CRICKET_PATTERNS = [
    # Test Cricket
    r"\btest\s+cricket\b",
    r"\btest\s+match(?:es)?\b",
    r"\btest\s+series\b",
    r"\bin\s+tests\b",
    r"\bin\s+test\s+matches\b",
    r"\btest\s+career\b",
    r"\btest\s+stats\b",
    r"\btest\s+centur(?:y|ies)\b",
    r"\btest\s+ranking(?:s)?\b",
    r"\btest\s+cap\b",
    r"\bworld\s+test\s+championship\b",
    r"\bwtc\b",
    r"\bthe\s+ashes\b",
    r"\bborder[- ]gavaskar\b",
    r"\branji(?:\s+trophy)?\b",
    r"\bduleep(?:\s+trophy)?\b",
    # ODI Cricket
    r"\bodis?\b",
    r"\bone[- ]day\s+international(?:s)?\b",
    r"\bone[- ]day\s+cricket\b",
    r"\b50[- ]over\s+cricket\b",
    r"\b50[- ]over\s+world\s+cup\b",
    r"\bcricket\s+world\s+cup\b",
    r"\bcwc\b",
    r"\bicc\s+world\s+cup\b",
    r"\bicc\s+cricket\s+world\s+cup\b",
    r"\bicc\s+champions\s+trophy\b",
    r"\bchampions\s+trophy\b",
    r"\basia\s+cup\b",
    # T20 Internationals
    r"\bt20is?\b",
    r"\bt20\s+international(?:s)?\b",
    r"\btwenty20\s+international(?:s)?\b",
    r"\bt20\s+world\s+cup\b",
    r"\bicc\s+t20\s+world\s+cup\b",
    # Other T20 / domestic leagues
    r"\bbbl\b",
    r"\bbig\s+bash(?:\s+league)?\b",
    r"\bpsl\b",
    r"\bpakistan\s+super\s+league\b",
    r"\bcpl\b",
    r"\bcaribbean\s+premier\s+league\b",
    r"\bthe\s+hundred\b",
    r"\bsa20\b",
    r"\bbpl\b",
    r"\bbangladesh\s+premier\s+league\b",
    r"\bilt20\b",
    r"\bvitality\s+blast\b",
    r"\bsuper\s+smash\b",
    r"\bmajor\s+league\s+cricket\b",
    r"\bmlc\b",
    r"\blpl\b",
    r"\blanka\s+premier\s+league\b",
]

# Non-cricket sports & tournaments
NON_CRICKET_SPORTS_PATTERNS = [
    # Football / Soccer
    r"\bfootball\b",
    r"\bfifa(?:\s+world\s+cup)?\b",
    r"\bsoccer\b",
    r"\bpremier\s+league\b",
    r"\bepl\b",
    r"\bla\s+liga\b",
    r"\bserie\s+a\b",
    r"\bbundesliga\b",
    r"\buefa\b",
    r"\bchampions\s+league\b",
    r"\bballon\s+d'?or\b",
    r"\bmessi\b",
    r"\bronaldo\b",
    r"\bmbappe\b",
    r"\bneymar\b",
    r"\bhaaland\b",
    r"\breal\s+madrid\b",
    r"\bbarcelona\b",
    r"\bmanchester\s+united\b",
    r"\barsenal\b",
    r"\bchelsea\b",
    r"\bliverpool\b",
    # Basketball
    r"\bnba\b",
    r"\bbasketball\b",
    r"\blebron(?:\s+james)?\b",
    r"\bstephen\s+curry\b",
    r"\blakers\b",
    r"\bceltics\b",
    r"\bwarriors\b",
    # Tennis
    r"\btennis\b",
    r"\bwimbledon\b",
    r"\broland\s+garros\b",
    r"\bus\s+open\b",
    r"\baustralian\s+open\b",
    r"\broger\s+federer\b",
    r"\brafael\s+nadal\b",
    r"\bnovak\s+djokovic\b",
    r"\bgrand\s+slam\b",
    # Formula 1 / Motorsports
    r"\bf1\b",
    r"\bformula\s+1\b",
    r"\blewis\s+hamilton\b",
    r"\bmax\s+verstappen\b",
    r"\bmotogp\b",
    # Other sports
    r"\bolympics?\b",
    r"\bbadminton\b",
    r"\bhockey\b",
    r"\bbaseball\b",
    r"\bmlb\b",
    r"\bnfl\b",
    r"\bsuper\s+bowl\b",
    r"\bamerican\s+football\b",
    r"\brugby\b",
    r"\bgolf\b",
    r"\bpga\b",
]

# Non-sports, technology, programming, mathematics & general knowledge
NON_CRICKET_GENERAL_PATTERNS = [
    # Programming / Software
    r"\bpython\b",
    r"\bjavascript\b",
    r"\btypescript\b",
    r"\breact\b",
    r"\bhtml\b",
    r"\bcss\b",
    r"\bjava\b",
    r"\bc\+\+\b",
    r"\bgolang\b",
    r"\bsql\s+query\b",
    r"\bcoding\b",
    r"\bprogramming\b",
    r"\balgorithm(?:s)?\b",
    r"\bquicksort\b",
    r"\bbubblesort\b",
    r"\bbinary\s+tree\b",
    r"\bdocker\b",
    r"\bkubernetes\b",
    r"\baws\b",
    r"\bazure\b",
    r"\bgcp\b",
    r"\bgit\b",
    r"\bgithub\b",
    # Mathematics & Science
    r"\bphotosynthesis\b",
    r"\bgravity\b",
    r"\bcalculus\b",
    r"\btrigonometry\b",
    r"\bderivative\b",
    r"\bintegral\b",
    r"\bsquare\s+root\b",
    # General knowledge / miscellaneous
    r"\bcapital\s+of\b",
    r"\bweather\s+in\b",
    r"\bpopulation\s+of\b",
    r"\bpresident\s+of\b",
    r"\bprime\s+minister\s+of\b",
    r"\bwho\s+wrote\b",
    r"\bwho\s+invented\b",
    r"\btell\s+me\s+a\s+joke\b",
    r"\bwrite\s+a\s+poem\b",
    r"\brecipe\s+for\b",
    r"\bmovie\b",
    r"\bactor\b",
    r"\bactress\b",
    r"\bbox\s+office\b",
]

RE_NON_IPL_REJECTIONS = re.compile(
    "|".join(
        NON_IPL_CRICKET_PATTERNS
        + NON_CRICKET_SPORTS_PATTERNS
        + NON_CRICKET_GENERAL_PATTERNS
    ),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 2. IPL Allowed Patterns (Fast Rule-Based Allow)
# ---------------------------------------------------------------------------

# Known IPL team keywords, abbreviations, and defunct franchises
IPL_TEAMS = [
    "royal challengers bengaluru",
    "royal challengers bangalore",
    "kolkata knight riders",
    "chennai super kings",
    "sunrisers hyderabad",
    "delhi daredevils",
    "delhi capitals",
    "kings xi punjab",
    "punjab kings",
    "rajasthan royals",
    "mumbai indians",
    "lucknow super giants",
    "gujarat titans",
    "deccan chargers",
    "kochi tuskers kerala",
    "kochi tuskers",
    "rising pune supergiants",
    "rising pune supergiant",
    "pune warriors india",
    "pune warriors",
    "gujarat lions",
    "csk",
    "rcb",
    "mi",
    "kkr",
    "srh",
    "lsg",
    "gt",
    "dc",
    "rr",
    "pbks",
    "kxip",
    "rps",
    "pwi",
    "ktk",
    "gl",
    "dec",
]

IPL_CONCEPTS = [
    r"\bipl\b",
    r"\bindian\s+premier\s+league\b",
    r"\btata\s+ipl\b",
    # Awards & Features
    r"\borange\s+cap\b",
    r"\bpurple\s+cap\b",
    r"\bemerging\s+player(?:\s+of\s+the\s+season)?\b",
    r"\bfair\s+play\s+award\b",
    r"\bmost\s+valuable\s+player\b",
    r"\bmvp\s+in\s+ipl\b",
    r"\bimpact\s+player(?:\s+rule)?\b",
    r"\bstrategic\s+time[- ]?out\b",
    # Auctions & Squads
    r"\bipl\s+auction(?:s)?\b",
    r"\bmega\s+auction(?:s)?\b",
    r"\bmini\s+auction(?:s)?\b",
    r"\bipl\s+retention(?:s)?\b",
    r"\bretention\s+rules?\b",
    r"\bright\s+to\s+match\b",
    r"\brtm\s+card\b",
    r"\bauction\s+purse\b",
    # Playoff stages
    r"\bqualifier\s+1\b",
    r"\bqualifier\s+2\b",
    r"\beliminator\b",
    r"\bipl\s+playoffs?\b",
    r"\bipl\s+final(?:s)?\b",
    r"\bipl\s+opening\s+match\b",
    r"\bipl\s+points\s+table\b",
    r"\bipl\s+standings\b",
    r"\bipl\s+records?\b",
    r"\bipl\s+history\b",
    r"\bipl\s+troph(?:y|ies)\b",
    r"\bipl\s+title(?:s)?\b",
    r"\bfirst\s+match\s+of\s+ipl\b",
    r"\binaugural\s+ipl\b",
]

RE_IPL_TEAMS = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in IPL_TEAMS) + r")\b",
    re.IGNORECASE,
)

RE_IPL_CONCEPTS = re.compile(
    "|".join(IPL_CONCEPTS),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 3. Anaphoric / Contextual Follow-up Detection
# ---------------------------------------------------------------------------

FOLLOW_UP_SIGNALS = [
    r"\b(?:he|him|his|she|her|they|them|their|it|its|this|that|these|those)\b",
    r"\bwhat\s+(?:about|was|is|did)\b",
    r"\bhow\s+(?:about|many|much)\b",
    r"\band\s+(?:in|who|what|which)\b",
    r"\bwho\s+(?:was|is|won|played)\b",
    r"\bwhich\s+team\b",
    r"\b(?:strike\s+rate|economy|average|captain|scorecard|runner[- ]up|highest\s+score)\b",
    r"\b(?:did\s+they|did\s+he|how\s+many\s+wickets|how\s+many\s+runs)\b",
]

RE_FOLLOW_UP = re.compile(
    "|".join(FOLLOW_UP_SIGNALS),
    re.IGNORECASE,
)


def _extract_recent_turns(
    conversation_history: Optional[List[Any]],
) -> List[Tuple[str, str]]:
    """
    Safely extract [(role, content), ...] pairs from heterogeneous history inputs
    (Pydantic models, dicts, or raw strings).
    """
    if not conversation_history:
        return []

    turns: List[Tuple[str, str]] = []
    for item in conversation_history:
        if isinstance(item, dict):
            role = str(item.get("role", "user"))
            content = str(item.get("content", ""))
            turns.append((role, content))
        elif hasattr(item, "role") and hasattr(item, "content"):
            role = str(getattr(item, "role", "user"))
            content = str(getattr(item, "content", ""))
            turns.append((role, content))
        elif isinstance(item, str):
            turns.append(("user", item))
    return turns


def is_ipl_context(conversation_history: Optional[List[Any]]) -> bool:
    """
    Returns True if the most recent turn in the conversation history was IPL-related.
    """
    turns = _extract_recent_turns(conversation_history)
    if not turns:
        return False

    # Inspect the most recent messages (up to last 2 turns)
    for role, content in reversed(turns[-2:]):
        # If the bot previously returned the restriction message, active context is NOT IPL
        if IPL_RESTRICTION_MESSAGE in content:
            return False

        # If previous user or bot message mentions IPL concepts or teams
        if RE_IPL_CONCEPTS.search(content) or RE_IPL_TEAMS.search(content):
            return True

    return False


def is_followup_question(question: str) -> bool:
    """
    Check if a question is an elliptical or anaphoric follow-up.
    """
    q = question.strip()
    words = q.split()

    # Short query or contains follow-up pronouns/elliptical phrases
    if RE_FOLLOW_UP.search(q):
        return True

    # Very short query without a full sentence structure (e.g., "in 2024?", "strike rate?")
    if len(words) <= 5 and any(w.endswith("?") for w in words):
        return True

    return False


# ---------------------------------------------------------------------------
# 4. Isolated Lightweight LLM Classifier
# ---------------------------------------------------------------------------

def _classify_with_llm(question: str, recent_context: str = "") -> bool:
    """
    Isolated lightweight LLM classifier for ambiguous queries.
    Cannot invoke tools, cannot perform RAG, cannot query SQL.
    Fails closed (returns False) on any network error, timeout, or exception.
    """
    prompt = (
        "You are a strict domain classifier for CricketGPT, an AI specialized exclusively "
        "in the Indian Premier League (IPL).\n"
        "Determine whether the following question is specifically about the IPL, including:\n"
        "- IPL franchises, teams, captains, squads, or team records\n"
        "- IPL players in an IPL tournament context\n"
        "- IPL matches, seasons (2008-2026), playoffs, points table, or standings\n"
        "- IPL statistics, records, or awards (Orange Cap, Purple Cap, etc.)\n"
        "- IPL auctions, player prices, or retention rules\n"
        "- Cricket rules that apply to IPL matches (e.g. Impact Player, LBW)\n"
        "- Direct follow-up questions to an active IPL conversation\n\n"
        "You must reject questions about international cricket (Tests, ODIs, T20 World Cups, "
        "bilateral series), other cricket leagues (BBL, PSL, The Hundred, CPL), other sports "
        "(football, basketball, tennis), programming, mathematics, or general knowledge.\n\n"
        f"Recent conversation context: {recent_context or 'None'}\n"
        f"Question: {question}\n\n"
        "Answer with ONLY 'YES' if the question is strictly IPL-related, or 'NO' if it is not."
    )

    try:
        from app.ai.llm.client import generate_response

        raw_result = generate_response(prompt)
        cleaned = raw_result.strip().upper()
        logger.info("IPL LLM classifier verdict for '%s': %s", question[:60], cleaned)
        return cleaned.startswith("YES")
    except Exception as exc:
        logger.warning(
            "IPL LLM classifier failed safely (failing closed): %s",
            str(exc)[:120],
        )
        return False


# ---------------------------------------------------------------------------
# 5. Main IPL Relevance Guard
# ---------------------------------------------------------------------------

def classify_ipl_domain(
    question: str,
    conversation_history: Optional[List[Any]] = None,
) -> Tuple[bool, str]:
    """
    Classify whether a question is within the IPL domain.

    Returns
    -------
    (is_ipl: bool, reason: str)
    """
    if not question or not question.strip():
        return False, "empty_question"

    q = question.strip()

    # Step A: Check for explicit Non-IPL rejection keywords
    # A new unrelated question must be rejected even if previous conversation was about IPL.
    if RE_NON_IPL_REJECTIONS.search(q):
        # Edge case: Does the query explicitly ask about IPL despite mentioning a non-IPL term?
        # e.g., "Do IPL players play in the World Cup?" vs "Who won the World Cup?"
        # The prompt says: "A player who participates in IPL and international cricket does
        # not make every question about that player IPL-related."
        # If the non-IPL term is an explicit target (e.g., Test cricket, ODI, FIFA, Football, PSL),
        # reject unless the question is explicitly focused on IPL with an IPL concept.
        has_ipl_anchor = bool(RE_IPL_CONCEPTS.search(q))
        if not has_ipl_anchor:
            return False, "non_ipl_domain_detected"

        # If both are present, check if the non-IPL term is an explicit non-cricket sport or code
        if bool(re.search(r"\b(?:football|fifa|messi|ronaldo|nba|tennis|python|javascript|quicksort)\b", q, re.I)):
            return False, "non_ipl_sport_or_tech"

    # Step B: Check for explicit IPL keywords or IPL Teams
    if RE_IPL_CONCEPTS.search(q):
        return True, "ipl_concept_matched"

    if RE_IPL_TEAMS.search(q):
        return True, "ipl_team_matched"

    # Step C: Contextual Follow-up Evaluation
    # If the current question lacks IPL keywords, check if it's a follow-up to an IPL conversation.
    has_active_ipl_context = is_ipl_context(conversation_history)
    if has_active_ipl_context:
        # Check if the question is an anaphoric / elliptical follow-up
        if is_followup_question(q):
            # Verify it does not introduce an unrelated topic
            if not RE_NON_IPL_REJECTIONS.search(q):
                return True, "contextual_ipl_followup"

    # Step D: Check for common cricket statistics/rules that default to IPL in CricketGPT
    # (unless an explicit non-IPL disqualifier was detected in Step A)
    # e.g. "Top 10 bowlers with dot balls", "Who scored 175 not out?", "Highest run scorers"
    has_cricket_stat_pattern = bool(
        re.search(
            r"\b(?:"
            r"orange\s+cap|purple\s+cap|fair\s+play|"
            r"highest\s+score|highest\s+individual\s+score|fastest\s+(?:fifty|century|100|50)|"
            r"most\s+(?:sixes|fours|boundaries|runs|wickets|centuries|fifties|hundreds)|"
            r"run\s+scorer(?:s)?|wicket\s+taker(?:s)?|"
            r"dot\s+balls?|bowler(?:s)?|bowling|batter(?:s)?|batsm[ae]n|batting|"
            r"strike\s+rate|economy(?:\s+rate)?|average|"
            r"scorecard|fall\s+of\s+wickets|last\s+over|"
            r"player\s+of\s+the\s+match|potm|man\s+of\s+the\s+match|"
            r"leaderboard(?:s)?|points\s+table|standings|"
            r"head\s+to\s+head|h2h|"
            r"hat[- ]trick|super\s+over|lbw|free\s+hit|no\s+ball"
            r")\b",
            q,
            re.IGNORECASE,
        )
    )
    if has_cricket_stat_pattern and not RE_NON_IPL_REJECTIONS.search(q):
        return True, "ipl_cricket_statistics_or_rule"

    # Step E: Ambiguous queries — isolate to lightweight LLM classifier
    recent_context_str = ""
    turns = _extract_recent_turns(conversation_history)
    if turns:
        recent_context_str = " | ".join(f"{role}: {text}" for role, text in turns[-2:])

    is_ipl = _classify_with_llm(q, recent_context=recent_context_str)
    if is_ipl:
        return True, "llm_classifier_confirmed_ipl"

    return False, "outside_ipl_domain"


def is_ipl_relevant(
    question: str,
    conversation_history: Optional[List[Any]] = None,
) -> bool:
    """
    Main entry point for IPL relevance check.
    Returns True if the question is IPL-related and should be answered.
    Returns False if the question is out of domain and should be rejected.
    """
    is_ipl, _ = classify_ipl_domain(question, conversation_history)
    return is_ipl
