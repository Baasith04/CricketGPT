"""Tests for the AI query router."""

import unittest
from unittest.mock import patch


class TestRouteQuestion(unittest.TestCase):
    """Test suite for route_question intent routing."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _route(self, question: str):
        from app.ai.query_router.router import route_question
        return route_question(question)

    # ------------------------------------------------------------------
    # Empty / blank input
    # ------------------------------------------------------------------

    def test_empty_question_returns_prompt(self):
        result = self._route("")
        self.assertIn("Please enter", result)

    def test_whitespace_question_returns_prompt(self):
        result = self._route("   ")
        self.assertIn("Please enter", result)

    # ------------------------------------------------------------------
    # Season winner (intent A)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_season_winner_question")
    def test_season_winner_routes_correctly(self, mock_fn):
        mock_fn.return_value = "CSK won 2023"
        result = self._route("Who won IPL 2023?")
        mock_fn.assert_called_once_with("2023")
        self.assertEqual(result, "CSK won 2023")

    @patch("app.ai.query_router.router.answer_season_winner_question")
    def test_season_winner_2007_08_alias(self, mock_fn):
        mock_fn.return_value = "RR won 2007/08"
        result = self._route("Who won IPL 2008 champion?")
        mock_fn.assert_called_once_with("2007/08")
        self.assertEqual(result, "RR won 2007/08")

    # ------------------------------------------------------------------
    # Match by ID — result (intent C)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_match_question")
    def test_match_id_result_routes_correctly(self, mock_fn):
        mock_fn.return_value = "MI won match 335982"
        result = self._route("Who won match 335982?")
        mock_fn.assert_called_once_with(335982, "Who won match 335982?")
        self.assertEqual(result, "MI won match 335982")

    # ------------------------------------------------------------------
    # Scorecard (intent C with scorecard keyword)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_scorecard_question")
    def test_scorecard_routes_correctly(self, mock_fn):
        mock_fn.return_value = "Scorecard for 335982"
        result = self._route("Show scorecard for match 335982")
        mock_fn.assert_called_once_with(335982)
        self.assertEqual(result, "Scorecard for 335982")

    # ------------------------------------------------------------------
    # Fall of wickets (intent C with wickets keyword)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_wickets_question")
    def test_fall_of_wickets_routes_correctly(self, mock_fn):
        mock_fn.return_value = "Wickets for 335982"
        result = self._route("Show fall of wickets in match 335982")
        mock_fn.assert_called_once_with(335982)
        self.assertEqual(result, "Wickets for 335982")

    # ------------------------------------------------------------------
    # Batting leaderboard (intent F)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_batting_leaderboard_runs_routes(self, mock_fn):
        mock_fn.return_value = "Runs leaderboard"
        result = self._route("Who scored the most runs in IPL?")
        mock_fn.assert_called_once_with(
            category="runs",
            question_type="batting",
            season=None,
            limit=10,
        )
        self.assertEqual(result, "Runs leaderboard")

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_batting_leaderboard_top_5(self, mock_fn):
        mock_fn.return_value = "Top 5 batters"
        self._route("Top 5 batsmen in IPL")
        call_kwargs = mock_fn.call_args.kwargs
        self.assertEqual(call_kwargs["limit"], 5)

    # ------------------------------------------------------------------
    # Bowling leaderboard (intent E)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_bowling_leaderboard_wickets_routes(self, mock_fn):
        mock_fn.return_value = "Wickets leaderboard"
        result = self._route("Most wickets in IPL")
        mock_fn.assert_called_once_with(
            category="wickets",
            question_type="bowling",
            season=None,
            limit=10,
        )
        self.assertEqual(result, "Wickets leaderboard")

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_bowling_leaderboard_economy_routes(self, mock_fn):
        mock_fn.return_value = "Economy leaderboard"
        self._route("Best economy in IPL bowling")
        call_kwargs = mock_fn.call_args.kwargs
        self.assertEqual(call_kwargs["category"], "economy")
        self.assertEqual(call_kwargs["question_type"], "bowling")

    # ------------------------------------------------------------------
    # Best bowling figures (intent D)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_best_bowling_figures_routes(self, mock_fn):
        mock_fn.return_value = "Best figures"
        result = self._route("Best bowling figures in IPL")
        mock_fn.assert_called_once_with(
            category="wickets",
            question_type="best_bowling",
            season=None,
            limit=10,
        )
        self.assertEqual(result, "Best figures")

    # ------------------------------------------------------------------
    # Player statistics (intent G)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_player_question")
    def test_player_stats_routes_correctly(self, mock_fn):
        mock_fn.return_value = "Virat Kohli stats"
        result = self._route("Show Virat Kohli batting statistics")
        mock_fn.assert_called_once()
        player_arg = mock_fn.call_args.args[0]
        self.assertIn("Kohli", player_arg)
        self.assertEqual(result, "Virat Kohli stats")

    @patch("app.ai.query_router.router.answer_player_question")
    def test_player_stats_possessive(self, mock_fn):
        mock_fn.return_value = "MS Dhoni stats"
        result = self._route("MS Dhoni's career stats")
        mock_fn.assert_called_once()
        player_arg = mock_fn.call_args.args[0]
        self.assertIn("Dhoni", player_arg)

    @patch("app.ai.query_router.router.answer_player_question")
    def test_player_bowling_stats_routes_to_player(self, mock_fn):
        mock_fn.return_value = "JJ Bumrah stats"
        result = self._route("Show Jasprit Bumrah bowling statistics")
        mock_fn.assert_called_once_with("Jasprit Bumrah")
        self.assertEqual(result, "JJ Bumrah stats")

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_top_run_scorer_for_team_routes_to_leaderboard(self, mock_fn):
        mock_fn.return_value = "Most runs leaderboard"
        result = self._route("Who scored the most runs for Mumbai Indians?")
        mock_fn.assert_called_once()
        self.assertEqual(result, "Most runs leaderboard")

    @patch("app.ai.query_router.router.answer_head_to_head_question")
    def test_between_teams_routes_to_h2h(self, mock_fn):
        mock_fn.return_value = "CSK vs MI"
        result = self._route("Head to head between CSK and MI")
        mock_fn.assert_called_once_with("csk", "mi")
        self.assertEqual(result, "CSK vs MI")

    # ------------------------------------------------------------------
    # Team statistics (intent H)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_team_question")
    def test_team_stats_routes_correctly(self, mock_fn):
        mock_fn.return_value = "MI stats"
        result = self._route("Show Mumbai Indians statistics")
        mock_fn.assert_called_once()
        self.assertEqual(result, "MI stats")

    @patch("app.ai.query_router.router.answer_team_question")
    def test_team_titles_routes_correctly(self, mock_fn):
        mock_fn.return_value = "CSK titles"
        result = self._route("How many IPL titles has CSK won?")
        mock_fn.assert_called_once()
        self.assertEqual(result, "CSK titles")

    # ------------------------------------------------------------------
    # Head-to-head (intent I)
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_head_to_head_question")
    def test_head_to_head_routes_correctly(self, mock_fn):
        mock_fn.return_value = "CSK vs MI H2H"
        result = self._route("CSK vs MI head-to-head record")
        mock_fn.assert_called_once()
        args = mock_fn.call_args.args
        self.assertEqual(len(args), 2)
        self.assertEqual(result, "CSK vs MI H2H")

    @patch("app.ai.query_router.router.answer_head_to_head_question")
    def test_versus_keyword_routes_to_h2h(self, mock_fn):
        mock_fn.return_value = "RCB vs MI"
        result = self._route("RCB versus MI record")
        mock_fn.assert_called_once()
        self.assertEqual(result, "RCB vs MI")

    @patch("app.ai.query_router.router.answer_head_to_head_question")
    def test_csk_vs_mi_head_to_head_without_season_preserves_h2h(self, mock_fn):
        mock_fn.return_value = "All-time H2H"
        result = self._route("CSK vs MI head-to-head")
        mock_fn.assert_called_once_with("csk", "mi")
        self.assertEqual(result, "All-time H2H")

    # ------------------------------------------------------------------
    # Season team-vs-team match results
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_team_versus_matches_question")
    def test_2024_csk_vs_mi_match_result_extracts_season_and_clean_teams(self, mock_fn):
        mock_fn.return_value = "2024 CSK vs MI result"
        result = self._route("2024 CSK vs MI match result")
        mock_fn.assert_called_once_with("csk", "mi", season="2024")
        self.assertEqual(result, "2024 CSK vs MI result")

    @patch("app.ai.query_router.router.answer_team_versus_matches_question")
    def test_2024_mi_vs_csk_match_result_reverse_order(self, mock_fn):
        mock_fn.return_value = "2024 MI vs CSK result"
        result = self._route("2024 MI vs CSK match result")
        mock_fn.assert_called_once_with("mi", "csk", season="2024")
        self.assertEqual(result, "2024 MI vs CSK result")

    @patch("app.ai.query_router.router.answer_team_versus_matches_question")
    def test_2023_csk_vs_mi_match_result(self, mock_fn):
        mock_fn.return_value = "2023 CSK vs MI results"
        result = self._route("2023 CSK vs MI match result")
        mock_fn.assert_called_once_with("csk", "mi", season="2023")
        self.assertEqual(result, "2023 CSK vs MI results")

    @patch("app.ai.query_router.router.answer_team_versus_matches_question")
    def test_season_with_no_matches_still_routes_to_season_versus(self, mock_fn):
        mock_fn.return_value = "No IPL 2099 matches found"
        result = self._route("2099 CSK vs MI match result")
        mock_fn.assert_called_once_with("csk", "mi", season="2099")
        self.assertIn("2099", result)

    @patch("app.ai.query_router.router.answer_team_versus_matches_question")
    def test_invalid_team_in_season_versus_routes_cleanly(self, mock_fn):
        mock_fn.return_value = "Match lookup error: Team 'xyz' was not found."
        result = self._route("2024 XYZ vs MI match result")
        mock_fn.assert_called_once_with("xyz", "mi", season="2024")
        self.assertIn("not found", result)


if __name__ == "__main__":
    unittest.main()

