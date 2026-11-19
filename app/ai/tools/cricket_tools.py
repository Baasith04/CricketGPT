"""
Cricket LangChain Tools — read-only wrappers around existing CricketGPT services.

Each tool is decorated with @tool and uses a Pydantic input schema for
validation.  All tools are read-only: no INSERT / UPDATE / DELETE, no raw DB
connections, 15 s timeout enforced at the service level.

Tool catalogue
--------------
1.  get_player_statistics        → batting + bowling career/season stats
2.  get_player_match_performance → scorecard filtered by player name
3.  compare_ipl_players          → head-to-head comparison (SQL)
4.  get_match_scorecard_tool     → full innings scorecard
5.  get_match_result_tool        → match result / winner details
6.  get_player_of_the_match      → POTM / match awards
7.  get_batting_leaderboard_tool → batting category leaderboard
8.  get_bowling_leaderboard_tool → bowling category leaderboard
9.  get_team_statistics_tool     → team performance statistics
10. search_cricket_knowledge     → hybrid pgvector + BM25 RAG retrieval
"""
from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.tools import tool  # type: ignore
from pydantic import BaseModel, Field  # pydantic v2 (matches existing project)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input schemas (Pydantic v2)
# ---------------------------------------------------------------------------

class PlayerStatsInput(BaseModel):
    player_name: str = Field(..., description="Full or partial IPL player name, e.g. 'Virat Kohli'.")
    season: Optional[str] = Field(None, description="IPL season year string, e.g. '2024'. Omit for career totals.")
    include_bowling: bool = Field(True, description="Whether to include bowling stats alongside batting stats.")


class PlayerMatchPerformanceInput(BaseModel):
    match_id: int = Field(..., description="Numeric IPL match ID, e.g. 1426312.")
    player_name: str = Field(..., description="Player name to filter from the full scorecard.")


class ComparePlayersInput(BaseModel):
    player_one: str = Field(..., description="First player's name.")
    player_two: str = Field(..., description="Second player's name.")
    season: Optional[str] = Field(None, description="Restrict comparison to a specific IPL season, e.g. '2024'.")


class MatchScorecardInput(BaseModel):
    match_id: int = Field(..., description="Numeric IPL match ID.")


class MatchResultInput(BaseModel):
    match_id: int = Field(..., description="Numeric IPL match ID.")


class PlayerOfTheMatchInput(BaseModel):
    match_id: Optional[int] = Field(None, description="Specific match ID. Provide at least one of match_id or season.")
    season: Optional[str] = Field(None, description="IPL season year, e.g. '2024'.")
    final_only: bool = Field(False, description="Set true to retrieve only the IPL Final POTM for the season.")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of POTM records to return.")


class BattingLeaderboardInput(BaseModel):
    category: str = Field(
        "runs",
        description=(
            "Batting stat category. One of: runs, sixes, fours, strike_rate, "
            "average, centuries, fifties."
        ),
    )
    season: Optional[str] = Field(None, description="Restrict to a specific IPL season, e.g. '2024'.")
    limit: int = Field(10, ge=1, le=50, description="Number of players to return.")


class BowlingLeaderboardInput(BaseModel):
    category: str = Field(
        "wickets",
        description=(
            "Bowling stat category. One of: wickets, economy, strike_rate, "
            "average, dot_balls, five_wickets."
        ),
    )
    season: Optional[str] = Field(None, description="Restrict to a specific IPL season, e.g. '2024'.")
    limit: int = Field(10, ge=1, le=50, description="Number of players to return.")


class TeamStatsInput(BaseModel):
    team: str = Field(..., description="IPL team name or abbreviation, e.g. 'CSK', 'Mumbai Indians'.")
    season: Optional[str] = Field(None, description="Restrict to a specific IPL season, e.g. '2024'.")


class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., description="Natural-language question to retrieve relevant IPL knowledge chunks.")
    top_k: int = Field(5, ge=1, le=20, description="Number of knowledge chunks to return.")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@tool(args_schema=PlayerStatsInput)
def get_player_statistics(
    player_name: str,
    season: Optional[str] = None,
    include_bowling: bool = True,
) -> str:
    """
    Retrieve IPL batting (and optionally bowling) statistics for a named player.
    Returns career totals when no season is specified.
    """
    try:
        from app.services.players.player_service import get_player_batting_stats
        batting = get_player_batting_stats(player_name, season=season)
        result = f"**Batting stats for {player_name}**\n{batting}"

        if include_bowling:
            try:
                from app.services.players.bowling_service import get_player_bowling_stats
                bowling = get_player_bowling_stats(player_name, season=season)
                result += f"\n\n**Bowling stats for {player_name}**\n{bowling}"
            except Exception:
                pass  # Batting-only player — not an error

        return result
    except Exception as exc:
        logger.warning("get_player_statistics failed for '%s': %s", player_name, str(exc)[:120])
        return f"Could not retrieve statistics for '{player_name}'."


@tool(args_schema=PlayerMatchPerformanceInput)
def get_player_match_performance(match_id: int, player_name: str) -> str:
    """
    Retrieve a specific player's batting and bowling performance in a single IPL match.
    """
    try:
        from app.services.matches.scorecard_service import get_match_scorecard
        scorecard = get_match_scorecard(match_id)
        if not scorecard:
            return f"No scorecard found for match {match_id}."

        # Filter batting rows
        player_lower = player_name.lower()
        batting_rows = [
            row for row in scorecard.get("batting", [])
            if player_lower in str(row.get("batter", "")).lower()
        ]
        bowling_rows = [
            row for row in scorecard.get("bowling", [])
            if player_lower in str(row.get("bowler", "")).lower()
        ]

        if not batting_rows and not bowling_rows:
            return f"No performance data found for '{player_name}' in match {match_id}."

        lines = [f"**{player_name} in Match {match_id}**"]
        if batting_rows:
            lines.append("\n*Batting*")
            for row in batting_rows:
                lines.append(
                    f"  {row.get('batter')} — {row.get('runs', 0)} runs off "
                    f"{row.get('balls_faced', 0)} balls, "
                    f"SR {row.get('strike_rate', 0)}"
                )
        if bowling_rows:
            lines.append("\n*Bowling*")
            for row in bowling_rows:
                lines.append(
                    f"  {row.get('bowler')} — {row.get('wickets', 0)}/{row.get('runs_conceded', 0)} "
                    f"in {row.get('overs', 0)} overs, "
                    f"economy {row.get('economy', 0)}"
                )
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("get_player_match_performance failed: %s", str(exc)[:120])
        return f"Could not retrieve performance data for match {match_id}."


@tool(args_schema=ComparePlayersInput)
def compare_ipl_players(
    player_one: str,
    player_two: str,
    season: Optional[str] = None,
) -> str:
    """
    Compare two IPL players' career or season statistics head-to-head.
    """
    try:
        from app.services.players.player_comparison_service import compare_players
        return compare_players(player_one, player_two, season=season)
    except Exception as exc:
        logger.warning("compare_ipl_players failed: %s", str(exc)[:120])
        return f"Could not compare '{player_one}' and '{player_two}'."


@tool(args_schema=MatchScorecardInput)
def get_match_scorecard_tool(match_id: int) -> str:
    """
    Retrieve the full batting and bowling scorecard for an IPL match by its numeric ID.
    """
    try:
        from app.ai.answer_service import answer_scorecard_question
        return answer_scorecard_question(match_id)
    except Exception as exc:
        logger.warning("get_match_scorecard_tool failed for match %d: %s", match_id, str(exc)[:120])
        return f"Could not retrieve scorecard for match {match_id}."


@tool(args_schema=MatchResultInput)
def get_match_result_tool(match_id: int) -> str:
    """
    Retrieve the result, winner, teams, date, and venue for a specific IPL match.
    """
    try:
        from app.services.matches.match_service import get_match_result
        result = get_match_result(match_id)
        if not result:
            return f"No match record found for match ID {match_id}."
        return (
            f"**Match {match_id}**\n"
            f"Season: {result.get('season')}\n"
            f"Date: {result.get('match_date')}\n"
            f"Teams: {result.get('team1')} vs {result.get('team2')}\n"
            f"Venue: {result.get('venue')}\n"
            f"Winner: {result.get('winner')}\n"
            f"Result: {result.get('result_type')} — "
            f"{result.get('win_by_runs') or result.get('win_by_wickets')} "
            f"{'runs' if result.get('win_by_runs') else 'wickets'}"
        )
    except Exception as exc:
        logger.warning("get_match_result_tool failed for match %d: %s", match_id, str(exc)[:120])
        return f"Could not retrieve result for match {match_id}."


@tool(args_schema=PlayerOfTheMatchInput)
def get_player_of_the_match(
    match_id: Optional[int] = None,
    season: Optional[str] = None,
    final_only: bool = False,
    limit: int = 10,
) -> str:
    """
    Retrieve Player of the Match award(s) for a specific match, season, or the IPL Final.
    """
    try:
        from app.ai.answer_service import answer_match_awards_question
        return answer_match_awards_question(
            match_id=match_id,
            season=season,
            final_only=final_only,
            limit=limit,
        )
    except Exception as exc:
        logger.warning("get_player_of_the_match failed: %s", str(exc)[:120])
        return "Could not retrieve Player of the Match data."


@tool(args_schema=BattingLeaderboardInput)
def get_batting_leaderboard_tool(
    category: str = "runs",
    season: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Retrieve an IPL batting leaderboard.
    Valid categories: runs, sixes, fours, strike_rate, average, centuries, fifties.
    """
    valid = {"runs", "sixes", "fours", "strike_rate", "average", "centuries", "fifties"}
    if category not in valid:
        return f"Invalid batting category '{category}'. Choose from: {', '.join(sorted(valid))}."
    try:
        from app.services.statistics.leaderboard_service import get_batting_leaderboard
        rows = get_batting_leaderboard(category=category, season=season, limit=limit)
        if not rows:
            qualifier = f"IPL {season}" if season else "IPL all-time"
            return f"No {qualifier} batting {category} data found."
        header = f"**Top {limit} {category} — {'IPL ' + season if season else 'All-Time IPL'}**\n"
        lines = []
        for i, row in enumerate(rows, 1):
            player = row.get("batter") or row.get("player") or row.get("player_name", "Unknown")
            value = row.get(category) or row.get("value") or row.get("total") or ""
            lines.append(f"{i}. {player} — {value}")
        return header + "\n".join(lines)
    except Exception as exc:
        logger.warning("get_batting_leaderboard_tool failed (category=%s): %s", category, str(exc)[:120])
        return f"Could not retrieve {category} batting leaderboard."


@tool(args_schema=BowlingLeaderboardInput)
def get_bowling_leaderboard_tool(
    category: str = "wickets",
    season: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Retrieve an IPL bowling leaderboard.
    Valid categories: wickets, economy, strike_rate, average, dot_balls, five_wickets.
    """
    valid = {"wickets", "economy", "strike_rate", "average", "dot_balls", "five_wickets"}
    if category not in valid:
        return f"Invalid bowling category '{category}'. Choose from: {', '.join(sorted(valid))}."
    try:
        from app.services.statistics.leaderboard_service import get_bowling_leaderboard
        rows = get_bowling_leaderboard(category=category, season=season, limit=limit)
        if not rows:
            qualifier = f"IPL {season}" if season else "IPL all-time"
            return f"No {qualifier} bowling {category} data found."
        header = f"**Top {limit} {category} — {'IPL ' + season if season else 'All-Time IPL'}**\n"
        lines = []
        for i, row in enumerate(rows, 1):
            player = row.get("bowler") or row.get("player") or row.get("player_name", "Unknown")
            value = row.get(category) or row.get("value") or row.get("total") or ""
            lines.append(f"{i}. {player} — {value}")
        return header + "\n".join(lines)
    except Exception as exc:
        logger.warning("get_bowling_leaderboard_tool failed (category=%s): %s", category, str(exc)[:120])
        return f"Could not retrieve {category} bowling leaderboard."


@tool(args_schema=TeamStatsInput)
def get_team_statistics_tool(team: str, season: Optional[str] = None) -> str:
    """
    Retrieve IPL performance statistics for a team — wins, losses, titles, NRR, etc.
    """
    try:
        from app.services.teams.team_statistics_service import get_individual_team_statistics
        return get_individual_team_statistics(team, season=season)
    except Exception as exc:
        logger.warning("get_team_statistics_tool failed for '%s': %s", team, str(exc)[:120])
        return f"Could not retrieve statistics for team '{team}'."


@tool(args_schema=KnowledgeSearchInput)
def search_cricket_knowledge(query: str, top_k: int = 5) -> str:
    """
    Search the CricketGPT knowledge base using hybrid vector + keyword retrieval.
    Use for rules, historical narratives, controversies, and contextual information
    not available in structured SQL tables.
    """
    try:
        from app.rag.retrieval.hybrid_retriever import hybrid_retrieve
        chunks = hybrid_retrieve(query, top_k=top_k)
        if not chunks:
            return "No relevant cricket knowledge found for your query."
        lines = [f"**Cricket Knowledge — Top {len(chunks)} results for:** _{query}_\n"]
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content") or chunk.get("text") or str(chunk)
            source = chunk.get("source") or chunk.get("document_title") or ""
            lines.append(f"**[{i}]** {source}\n{content[:500]}")
        return "\n\n".join(lines)
    except Exception as exc:
        logger.warning("search_cricket_knowledge failed: %s", str(exc)[:120])
        return "Knowledge base search is temporarily unavailable."


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------
ALL_CRICKET_TOOLS = [
    get_player_statistics,
    get_player_match_performance,
    compare_ipl_players,
    get_match_scorecard_tool,
    get_match_result_tool,
    get_player_of_the_match,
    get_batting_leaderboard_tool,
    get_bowling_leaderboard_tool,
    get_team_statistics_tool,
    search_cricket_knowledge,
]

