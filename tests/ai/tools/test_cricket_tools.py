"""
Tests for CricketGPT LangChain cricket tools.

All service calls are mocked — no real database or API access.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Tool import helper
# ---------------------------------------------------------------------------

def _tools():
    from app.ai.tools.cricket_tools import (
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
        ALL_CRICKET_TOOLS,
    )
    return (
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
        ALL_CRICKET_TOOLS,
    )


# ---------------------------------------------------------------------------
# 1. get_player_statistics
# ---------------------------------------------------------------------------

class TestGetPlayerStatistics:
    def test_returns_batting_and_bowling(self):
        (get_player_statistics, *_) = _tools()
        with (
            patch("app.services.players.player_service.get_player_batting_stats",
                  return_value="Batting data") as mb,
            patch("app.services.players.bowling_service.get_player_bowling_stats",
                  return_value="Bowling data") as mw,
        ):
            result = get_player_statistics.invoke({
                "player_name": "Virat Kohli",
                "season": "2024",
                "include_bowling": True,
            })
            assert "Batting data" in result
            assert "Bowling data" in result

    def test_missing_bowling_handled_gracefully(self):
        (get_player_statistics, *_) = _tools()
        with (
            patch("app.services.players.player_service.get_player_batting_stats",
                  return_value="Batting data"),
            patch("app.services.players.bowling_service.get_player_bowling_stats",
                  side_effect=Exception("no bowling")),
        ):
            result = get_player_statistics.invoke({
                "player_name": "Rohit Sharma",
                "include_bowling": True,
            })
            assert "Batting data" in result
            assert "Bowling data" not in result

    def test_service_failure_returns_error_message(self):
        (get_player_statistics, *_) = _tools()
        with patch(
            "app.services.players.player_service.get_player_batting_stats",
            side_effect=RuntimeError("DB error"),
        ):
            result = get_player_statistics.invoke({"player_name": "Nobody"})
            assert "Could not retrieve" in result


# ---------------------------------------------------------------------------
# 2. get_player_match_performance
# ---------------------------------------------------------------------------

class TestGetPlayerMatchPerformance:
    def test_filters_by_player_name(self):
        (_, get_player_match_performance, *_) = _tools()
        fake_scorecard = {
            "batting": [
                {"batter": "MS Dhoni", "runs": 75, "balls_faced": 50, "strike_rate": 150},
                {"batter": "Virat Kohli", "runs": 20, "balls_faced": 18, "strike_rate": 111},
            ],
            "bowling": [
                {"bowler": "Jasprit Bumrah", "wickets": 2, "runs_conceded": 25, "overs": 4, "economy": 6.25},
            ],
        }
        with patch(
            "app.services.matches.scorecard_service.get_match_scorecard",
            return_value=fake_scorecard,
        ):
            result = get_player_match_performance.invoke({
                "match_id": 12345,
                "player_name": "MS Dhoni",
            })
            assert "MS Dhoni" in result
            assert "75" in result
            assert "Virat Kohli" not in result

    def test_no_scorecard_returns_message(self):
        (_, get_player_match_performance, *_) = _tools()
        with patch(
            "app.services.matches.scorecard_service.get_match_scorecard",
            return_value=None,
        ):
            result = get_player_match_performance.invoke({
                "match_id": 99999,
                "player_name": "MS Dhoni",
            })
            assert "No scorecard" in result

    def test_player_not_in_match(self):
        (_, get_player_match_performance, *_) = _tools()
        with patch(
            "app.services.matches.scorecard_service.get_match_scorecard",
            return_value={"batting": [], "bowling": []},
        ):
            result = get_player_match_performance.invoke({
                "match_id": 12345,
                "player_name": "Sachin Tendulkar",
            })
            assert "No performance data" in result


# ---------------------------------------------------------------------------
# 3. compare_ipl_players
# ---------------------------------------------------------------------------

class TestCompareIPLPlayers:
    def test_calls_comparison_service(self):
        (_, _, compare_ipl_players, *_) = _tools()
        with patch(
            "app.services.players.player_comparison_service.compare_players",
            return_value="Comparison result",
        ) as mock_cmp:
            result = compare_ipl_players.invoke({
                "player_one": "Kohli",
                "player_two": "Rohit",
                "season": "2024",
            })
            assert result == "Comparison result"
            mock_cmp.assert_called_once_with("Kohli", "Rohit", season="2024")

    def test_service_failure_handled(self):
        (_, _, compare_ipl_players, *_) = _tools()
        with patch(
            "app.services.players.player_comparison_service.compare_players",
            side_effect=RuntimeError("DB error"),
        ):
            result = compare_ipl_players.invoke({
                "player_one": "A", "player_two": "B"
            })
            assert "Could not compare" in result


# ---------------------------------------------------------------------------
# 4. get_match_scorecard_tool
# ---------------------------------------------------------------------------

class TestGetMatchScorecardTool:
    def test_calls_answer_scorecard(self):
        (_, _, _, get_match_scorecard_tool, *_) = _tools()
        with patch(
            "app.ai.answer_service.answer_scorecard_question",
            return_value="Full scorecard here",
        ):
            result = get_match_scorecard_tool.invoke({"match_id": 1426312})
            assert result == "Full scorecard here"

    def test_service_failure_handled(self):
        (_, _, _, get_match_scorecard_tool, *_) = _tools()
        with patch(
            "app.ai.answer_service.answer_scorecard_question",
            side_effect=RuntimeError("Not found"),
        ):
            result = get_match_scorecard_tool.invoke({"match_id": 99999})
            assert "Could not retrieve scorecard" in result


# ---------------------------------------------------------------------------
# 5. get_match_result_tool
# ---------------------------------------------------------------------------

class TestGetMatchResultTool:
    def test_formats_result(self):
        (_, _, _, _, get_match_result_tool, *_) = _tools()
        fake = {
            "season": "2024",
            "match_date": "2024-05-26",
            "team1": "SRH",
            "team2": "KKR",
            "venue": "MA Chidambaram Stadium",
            "winner": "KKR",
            "result_type": "wickets",
            "win_by_wickets": 8,
            "win_by_runs": None,
        }
        with patch(
            "app.services.matches.match_service.get_match_result",
            return_value=fake,
        ):
            result = get_match_result_tool.invoke({"match_id": 1426312})
            assert "KKR" in result
            assert "2024-05-26" in result

    def test_missing_match_returns_message(self):
        (_, _, _, _, get_match_result_tool, *_) = _tools()
        with patch(
            "app.services.matches.match_service.get_match_result",
            return_value=None,
        ):
            result = get_match_result_tool.invoke({"match_id": 99999})
            assert "No match record" in result


# ---------------------------------------------------------------------------
# 6. get_player_of_the_match
# ---------------------------------------------------------------------------

class TestGetPlayerOfTheMatch:
    def test_calls_awards_service(self):
        (_, _, _, _, _, get_player_of_the_match, *_) = _tools()
        with patch(
            "app.ai.answer_service.answer_match_awards_question",
            return_value="🏆 Player of the Match: MA Starc",
        ):
            result = get_player_of_the_match.invoke({
                "match_id": 1426312,
                "season": None,
                "final_only": False,
                "limit": 1,
            })
            assert "MA Starc" in result

    def test_service_error_handled(self):
        (_, _, _, _, _, get_player_of_the_match, *_) = _tools()
        with patch(
            "app.ai.answer_service.answer_match_awards_question",
            side_effect=RuntimeError("DB error"),
        ):
            result = get_player_of_the_match.invoke({"limit": 5})
            assert "Could not retrieve" in result


# ---------------------------------------------------------------------------
# 7. get_batting_leaderboard_tool
# ---------------------------------------------------------------------------

class TestGetBattingLeaderboardTool:
    def test_valid_category_returns_data(self):
        (_, _, _, _, _, _, get_batting_leaderboard_tool, *_) = _tools()
        rows = [
            {"batter": "Virat Kohli", "runs": 973},
            {"batter": "Ruturaj Gaikwad", "runs": 583},
        ]
        with patch(
            "app.services.statistics.leaderboard_service.get_batting_leaderboard",
            return_value=rows,
        ):
            result = get_batting_leaderboard_tool.invoke({
                "category": "runs",
                "season": "2024",
                "limit": 2,
            })
            assert "Virat Kohli" in result

    def test_invalid_category_returns_error(self):
        (_, _, _, _, _, _, get_batting_leaderboard_tool, *_) = _tools()
        result = get_batting_leaderboard_tool.invoke({
            "category": "nonsense",
            "limit": 10,
        })
        assert "Invalid batting category" in result

    def test_empty_result_handled(self):
        (_, _, _, _, _, _, get_batting_leaderboard_tool, *_) = _tools()
        with patch(
            "app.services.statistics.leaderboard_service.get_batting_leaderboard",
            return_value=[],
        ):
            result = get_batting_leaderboard_tool.invoke({"category": "runs"})
            assert "No" in result


# ---------------------------------------------------------------------------
# 8. get_bowling_leaderboard_tool
# ---------------------------------------------------------------------------

class TestGetBowlingLeaderboardTool:
    def test_valid_category_returns_data(self):
        (_, _, _, _, _, _, _, get_bowling_leaderboard_tool, *_) = _tools()
        rows = [{"bowler": "Jasprit Bumrah", "wickets": 20}]
        with patch(
            "app.services.statistics.leaderboard_service.get_bowling_leaderboard",
            return_value=rows,
        ):
            result = get_bowling_leaderboard_tool.invoke({
                "category": "wickets",
                "limit": 1,
            })
            assert "Bumrah" in result

    def test_invalid_category_rejected(self):
        (_, _, _, _, _, _, _, get_bowling_leaderboard_tool, *_) = _tools()
        result = get_bowling_leaderboard_tool.invoke({"category": "magic"})
        assert "Invalid bowling category" in result

    def test_dot_balls_category_accepted(self):
        (_, _, _, _, _, _, _, get_bowling_leaderboard_tool, *_) = _tools()
        with patch(
            "app.services.statistics.leaderboard_service.get_bowling_leaderboard",
            return_value=[{"bowler": "Test Bowler", "dot_balls": 500}],
        ):
            result = get_bowling_leaderboard_tool.invoke({
                "category": "dot_balls",
                "limit": 5,
            })
            assert "Test Bowler" in result


# ---------------------------------------------------------------------------
# 9. get_team_statistics_tool
# ---------------------------------------------------------------------------

class TestGetTeamStatisticsTool:
    def test_calls_team_service(self):
        (_, _, _, _, _, _, _, _, get_team_statistics_tool, *_) = _tools()
        with patch(
            "app.services.teams.team_statistics_service.get_individual_team_statistics",
            return_value="CSK stats data",
        ):
            result = get_team_statistics_tool.invoke({"team": "CSK", "season": "2024"})
            assert result == "CSK stats data"

    def test_service_error_handled(self):
        (_, _, _, _, _, _, _, _, get_team_statistics_tool, *_) = _tools()
        with patch(
            "app.services.teams.team_statistics_service.get_individual_team_statistics",
            side_effect=RuntimeError("DB error"),
        ):
            result = get_team_statistics_tool.invoke({"team": "CSK"})
            assert "Could not retrieve" in result


# ---------------------------------------------------------------------------
# 10. search_cricket_knowledge
# ---------------------------------------------------------------------------

class TestSearchCricketKnowledge:
    def test_returns_formatted_chunks(self):
        (*_, search_cricket_knowledge, _) = _tools()
        fake_chunks = [
            {"content": "DLS method explanation...", "source": "IPL Rules 2024"},
            {"content": "Impact player rule...", "source": "IPL Regulations"},
        ]
        with patch(
            "app.rag.retrieval.hybrid_retriever.hybrid_retrieve",
            return_value=fake_chunks,
        ):
            result = search_cricket_knowledge.invoke({
                "query": "What is the DLS method?",
                "top_k": 2,
            })
            assert "DLS method" in result
            assert "IPL Rules 2024" in result

    def test_empty_result_message(self):
        (*_, search_cricket_knowledge, _) = _tools()
        with patch(
            "app.rag.retrieval.hybrid_retriever.hybrid_retrieve",
            return_value=[],
        ):
            result = search_cricket_knowledge.invoke({"query": "unknown query"})
            assert "No relevant" in result

    def test_service_error_handled(self):
        (*_, search_cricket_knowledge, _) = _tools()
        with patch(
            "app.rag.retrieval.hybrid_retriever.hybrid_retrieve",
            side_effect=RuntimeError("RAG error"),
        ):
            result = search_cricket_knowledge.invoke({"query": "test"})
            assert "unavailable" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# ALL_CRICKET_TOOLS catalog test
# ---------------------------------------------------------------------------

class TestToolCatalog:
    def test_ten_tools_exported(self):
        (*_, ALL_CRICKET_TOOLS) = _tools()
        assert len(ALL_CRICKET_TOOLS) == 10

    def test_all_tools_have_names(self):
        (*_, ALL_CRICKET_TOOLS) = _tools()
        names = [t.name for t in ALL_CRICKET_TOOLS]
        assert "get_player_statistics" in names
        assert "search_cricket_knowledge" in names
        assert "get_batting_leaderboard_tool" in names
        assert "get_bowling_leaderboard_tool" in names
        assert "get_player_of_the_match" in names

