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

    # ------------------------------------------------------------------
    # Extended Batting, Bowling, Player, Team, Match, Advanced intents
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_highest_batting_average_routes_to_leaderboard(self, mock_fn):
        mock_fn.return_value = "Average leaderboard"
        self._route("Who has the highest batting average?")
        mock_fn.assert_called_once_with(
            category="average",
            question_type="batting",
            season=None,
            limit=10,
        )

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_most_centuries_routes_to_leaderboard(self, mock_fn):
        mock_fn.return_value = "Centuries leaderboard"
        self._route("Who scored the most centuries?")
        mock_fn.assert_called_once_with(
            category="centuries",
            question_type="batting",
            season=None,
            limit=10,
        )

    @patch("app.ai.query_router.router.answer_highest_individual_scores_question")
    def test_highest_individual_scores_routes(self, mock_fn):
        mock_fn.return_value = "Individual scores"
        self._route("Show the highest individual scores.")
        mock_fn.assert_called_once_with(season=None, limit=10)

    @patch("app.ai.query_router.router.answer_boundaries_combined_question")
    def test_sixes_and_fours_combined_routes(self, mock_fn):
        mock_fn.return_value = "Sixes and fours"
        self._route("Who scored the most sixes and fours?")
        mock_fn.assert_called_once_with(season=None, limit=10)

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_most_five_wicket_hauls_routes(self, mock_fn):
        mock_fn.return_value = "5w hauls"
        self._route("Who has the most five-wicket hauls?")
        mock_fn.assert_called_once_with(
            category="five_wickets",
            question_type="bowling",
            season=None,
            limit=10,
        )

    @patch("app.ai.query_router.router.answer_player_question")
    def test_player_runs_in_season_routes_with_season(self, mock_fn):
        mock_fn.return_value = "Kohli 2024"
        self._route("How many runs did Virat Kohli score in 2024?")
        mock_fn.assert_called_once_with("Virat Kohli", season="2024")

    @patch("app.ai.query_router.router.answer_player_question")
    def test_player_matches_played_routes(self, mock_fn):
        mock_fn.return_value = "Dhoni matches"
        self._route("How many matches has MS Dhoni played?")
        mock_fn.assert_called_once_with("MS Dhoni")

    @patch("app.ai.query_router.router.answer_player_comparison_question")
    def test_compare_players_routes(self, mock_fn):
        mock_fn.return_value = "Comparison"
        self._route("Compare Kohli and Rohit Sharma.")
        mock_fn.assert_called_once_with("Kohli", "Rohit Sharma")

    @patch("app.ai.query_router.router.answer_player_season_breakdown_question")
    def test_player_season_wise_routes(self, mock_fn):
        mock_fn.return_value = "Season breakdown"
        self._route("Show Virat Kohli's season-wise performance.")
        mock_fn.assert_called_once_with("Virat Kohli")

    @patch("app.ai.query_router.router.answer_team_question")
    def test_team_wins_in_season_routes_with_season(self, mock_fn):
        mock_fn.return_value = "CSK 2024"
        self._route("How many matches did CSK win in 2024?")
        mock_fn.assert_called_once_with("csk", season="2024")

    @patch("app.ai.query_router.router.answer_team_runs_leaderboard_question")
    def test_which_team_scored_most_runs_routes(self, mock_fn):
        mock_fn.return_value = "Team runs"
        self._route("Which team scored the most runs?")
        mock_fn.assert_called_once_with(season=None, limit=10)

    @patch("app.ai.query_router.router.answer_most_titles_question")
    def test_which_team_most_titles_routes(self, mock_fn):
        mock_fn.return_value = "Team titles"
        self._route("Which team has won the most IPL titles?")
        mock_fn.assert_called_once_with()

    @patch("app.ai.query_router.router.answer_head_to_head_question")
    def test_beaten_phrasing_routes_to_h2h(self, mock_fn):
        mock_fn.return_value = "H2H"
        self._route("How many times has CSK beaten MI?")
        mock_fn.assert_called_once_with("csk", "mi")

    @patch("app.ai.query_router.router.answer_match_by_date_question")
    def test_match_by_date_routes(self, mock_fn):
        import datetime
        mock_fn.return_value = "Date match"
        self._route("What was the result of the CSK vs MI match on 2024-04-14?")
        mock_fn.assert_called_once()
        self.assertEqual(mock_fn.call_args.kwargs["match_date"], datetime.date(2024, 4, 14))
        self.assertEqual(mock_fn.call_args.kwargs["team_one"], "csk")
        self.assertEqual(mock_fn.call_args.kwargs["team_two"], "mi")

    @patch("app.ai.query_router.router.answer_match_awards_question")
    def test_potm_with_match_id_routes(self, mock_fn):
        mock_fn.return_value = "POTM"
        self._route("Who was player of the match in match 335982?")
        mock_fn.assert_called_once_with(match_id=335982)

    @patch("app.ai.query_router.router.answer_last_over_question")
    def test_last_over_with_match_id_routes(self, mock_fn):
        mock_fn.return_value = "Last over"
        self._route("What happened in the last over of match 335982?")
        mock_fn.assert_called_once_with(335982)

    def test_ambiguous_scorecard_without_match_prompts_specifically(self):
        result = self._route("Show the scorecard.")
        self.assertIn("match ID", result)

    @patch("app.ai.query_router.router.answer_highest_chases_question")
    def test_highest_run_chase_routes(self, mock_fn):
        mock_fn.return_value = "Chases"
        self._route("Highest successful run chase.")
        mock_fn.assert_called_once_with(season=None, limit=10)

    @patch("app.ai.query_router.router.answer_biggest_victories_question")
    def test_biggest_victory_by_wickets_routes(self, mock_fn):
        mock_fn.return_value = "Big win"
        self._route("Biggest victory by wickets.")
        mock_fn.assert_called_once_with(by="wickets", season=None, limit=10)

    @patch("app.ai.query_router.router.answer_team_totals_question")
    def test_lowest_team_totals_routes(self, mock_fn):
        mock_fn.return_value = "Lowest totals"
        self._route("Lowest team totals.")
        mock_fn.assert_called_once_with(highest=False, season=None, limit=10)

    @patch("app.ai.query_router.router.answer_most_sixes_innings_question")
    def test_most_sixes_in_innings_routes(self, mock_fn):
        mock_fn.return_value = "Sixes innings"
        self._route("Most sixes in an innings.")
        mock_fn.assert_called_once_with(season=None, limit=10)

    @patch("app.ai.query_router.router.answer_phase_stats_question")
    def test_death_over_bowling_stats_routes(self, mock_fn):
        mock_fn.return_value = "Death bowling"
        self._route("Death-over bowling statistics.")
        mock_fn.assert_called_once_with(phase="death", stat_type="bowling", season=None, limit=10)

    @patch("app.ai.query_router.router.answer_extras_dismissals_question")
    def test_extras_and_dismissals_routes(self, mock_fn):
        mock_fn.return_value = "Extras"
        self._route("Extras and dismissal statistics.")
        mock_fn.assert_called_once_with(season=None)

    # ------------------------------------------------------------------
    # Knowledge-cutoff routing, multi-season, comparisons & relative dates
    # ------------------------------------------------------------------

    @patch("app.ai.query_router.router.answer_historical_llm_question")
    def test_within_cutoff_campaign_uses_gemini_directly_without_rag(self, mock_hist):
        mock_hist.return_value = "RR 2008 campaign narrative"
        result = self._route("Explain Rajasthan Royals' 2008 campaign.")
        mock_hist.assert_called_once_with(
            "Explain Rajasthan Royals' 2008 campaign.",
            seasons=["2007/08"],
            team_identifier="rajasthan royals",
        )
        self.assertEqual(result, "RR 2008 campaign narrative")

    @patch("app.ai.query_router.router.answer_season_winner_question")
    def test_within_cutoff_exact_winner_still_uses_sql(self, mock_winner):
        mock_winner.return_value = "Deccan Chargers won 2009"
        result = self._route("Who won IPL 2009?")
        mock_winner.assert_called_once_with("2009")
        self.assertEqual(result, "Deccan Chargers won 2009")

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_post_cutoff_most_runs_routes_to_sql(self, mock_lb):
        mock_lb.return_value = "2026 runs leaderboard"
        result = self._route("Who scored the most runs in IPL 2026?")
        mock_lb.assert_called_once_with(
            category="runs",
            question_type="batting",
            season="2026",
            limit=10,
        )
        self.assertEqual(result, "2026 runs leaderboard")

    @patch("app.ai.query_router.router.answer_rag_narrative_question")
    def test_post_cutoff_final_narrative_routes_to_rag(self, mock_rag):
        mock_rag.return_value = "RAG 2026 final"
        result = self._route("Explain the IPL 2026 final.")
        mock_rag.assert_called_once_with("Explain the IPL 2026 final.", season="2026")
        self.assertEqual(result, "RAG 2026 final")

    @patch("app.ai.query_router.router.answer_cross_boundary_question")
    def test_cross_cutoff_season_comparison_extracts_both_seasons(self, mock_cross):
        mock_cross.return_value = "Cross-boundary 2016 vs 2026"
        result = self._route("Compare IPL 2016 and IPL 2026.")
        mock_cross.assert_called_once()
        kwargs = mock_cross.call_args.kwargs
        self.assertEqual(kwargs["seasons"], ["2016", "2026"])
        self.assertEqual(kwargs["cutoff_info"]["scope"], "cross_cutoff")
        self.assertEqual(result, "Cross-boundary 2016 vs 2026")

    @patch("app.ai.query_router.router.answer_player_multi_season_comparison_question")
    def test_cross_cutoff_single_player_multi_season_comparison(self, mock_ms):
        mock_ms.return_value = "Kohli 2023 vs 2026"
        result = self._route("Compare Kohli's performance in 2023 and 2026.")
        mock_ms.assert_called_once()
        args = mock_ms.call_args.args
        kwargs = mock_ms.call_args.kwargs
        self.assertEqual(args[1], "Kohli")
        self.assertEqual(args[2], ["2023", "2026"])
        self.assertEqual(kwargs["cutoff_info"]["scope"], "cross_cutoff")
        self.assertEqual(result, "Kohli 2023 vs 2026")

    @patch("app.ai.query_router.router.answer_player_comparison_question")
    def test_two_player_season_comparison_without_explanation_uses_sql_not_rag(self, mock_sql_cmp):
        mock_sql_cmp.return_value = "SQL Kohli vs Rohit 2024"
        result = self._route("Compare Kohli and Rohit in 2024")
        mock_sql_cmp.assert_called_once_with("Kohli", "Rohit", season="2024")
        self.assertEqual(result, "SQL Kohli vs Rohit 2024")

    @patch("app.ai.query_router.router.answer_rag_narrative_question")
    def test_team_history_not_intercepted_by_team_stats(self, mock_rag):
        mock_rag.return_value = "MI history"
        result = self._route("IPL history of MI")
        mock_rag.assert_called_once_with("IPL history of MI", season=None)
        self.assertEqual(result, "MI history")

    @patch("app.ai.query_router.router.answer_post_cutoff_overview_question")
    @patch("app.ai.query_router.router.get_latest_season", return_value="2026")
    def test_relative_latest_season_overview_resolves_latest_season(self, mock_latest, mock_post):
        mock_post.return_value = "Latest 2026 overview"
        result = self._route("What happened in the latest IPL season?")
        mock_latest.assert_called_once_with()
        mock_post.assert_called_once_with(
            "What happened in the latest IPL season?",
            season="2026",
        )
        self.assertEqual(result, "Latest 2026 overview")

    @patch("app.ai.query_router.router.answer_leaderboard_question")
    @patch("app.ai.query_router.router.get_latest_season", return_value="2026")
    def test_relative_current_season_most_runs_resolves_to_sql(self, mock_latest, mock_lb):
        mock_lb.return_value = "Current runs leaderboard"
        result = self._route("Who scored the most runs in the current season?")
        mock_latest.assert_called_once_with()
        mock_lb.assert_called_once_with(
            category="runs",
            question_type="batting",
            season="2026",
            limit=10,
        )
        self.assertEqual(result, "Current runs leaderboard")

    @patch("app.ai.query_router.router.answer_rag_narrative_question")
    def test_ambiguous_unbounded_query_uses_supabase_rather_than_guessing(self, mock_rag):
        mock_rag.return_value = "RAG grounded fallback"
        result = self._route("Tell me about recent IPL impact sub impact")
        mock_rag.assert_called_once()
        self.assertEqual(result, "RAG grounded fallback")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2015", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2016-01-01"})
    @patch("app.ai.query_router.router.answer_rag_narrative_question")
    def test_custom_env_cutoff_shifts_routing_boundary(self, mock_rag):
        mock_rag.return_value = "2018 routed to RAG under 2015 cutoff"
        result = self._route("Explain CSK's 2018 campaign.")
        mock_rag.assert_called_once_with("Explain CSK's 2018 campaign.", season="2018")
        self.assertEqual(result, "2018 routed to RAG under 2015 cutoff")

    def test_extract_query_entities_handles_multi_season_and_since_ranges(self):
        from app.ai.query_router.router import extract_query_entities
        entities = extract_query_entities("Compare CSK since 2018 and 2026")
        self.assertEqual(entities["seasons"], ["2018", "2026"])
        self.assertTrue(entities["has_since_range"])
        self.assertEqual(entities["cutoff"]["scope"], "cross_cutoff")

        since_only = extract_query_entities("How has MI performed since 2020?")
        self.assertEqual(since_only["seasons"], ["2020/21"])
        self.assertEqual(since_only["cutoff"]["scope"], "cross_cutoff")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    @patch("app.ai.query_router.router.answer_playoff_match_question")
    def test_ipl_2024_final_scorecard_uses_sql_even_within_cutoff(
        self, mock_playoff, mock_hist
    ):
        mock_playoff.return_value = "IPL 2024 Final Scorecard [SQL]"
        result = self._route("Give me the IPL 2024 final scorecard.")
        mock_playoff.assert_called_once_with("2024", "final", detail_type="scorecard")
        mock_hist.assert_not_called()
        self.assertEqual(result, "IPL 2024 Final Scorecard [SQL]")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    @patch("app.ai.query_router.router.answer_playoff_match_question")
    def test_ipl_2023_final_scorecard_uses_sql(
        self, mock_playoff, mock_hist
    ):
        mock_playoff.return_value = "IPL 2023 Final Scorecard [SQL]"
        result = self._route("Give me the IPL 2023 final scorecard.")
        mock_playoff.assert_called_once_with("2023", "final", detail_type="scorecard")
        mock_hist.assert_not_called()
        self.assertEqual(result, "IPL 2023 Final Scorecard [SQL]")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_season_winner_question")
    def test_ipl_2008_winner_routes_to_sql_winner(self, mock_winner):
        mock_winner.return_value = "Rajasthan Royals won IPL 2007/08."
        result = self._route("Who won IPL 2008?")
        mock_winner.assert_called_once_with("2007/08")
        self.assertEqual(result, "Rajasthan Royals won IPL 2007/08.")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_rag_narrative_question")
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    def test_rajasthan_royals_2008_campaign_routes_to_historical_llm(
        self, mock_hist, mock_rag
    ):
        mock_hist.return_value = "RR 2008 campaign [Gemini Historical Knowledge]"
        result = self._route("Explain Rajasthan Royals' 2008 campaign")
        mock_hist.assert_called_once()
        mock_rag.assert_not_called()
        self.assertEqual(result, "RR 2008 campaign [Gemini Historical Knowledge]")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    @patch("app.ai.query_router.router.answer_leaderboard_question")
    def test_most_runs_ipl_2024_uses_sql_even_within_cutoff(
        self, mock_lb, mock_hist
    ):
        mock_lb.return_value = "Top run scorers in IPL 2024 [SQL]"
        result = self._route("Who scored the most runs in IPL 2024?")
        mock_lb.assert_called_once_with(
            category="runs",
            question_type="batting",
            season="2024",
            limit=10,
        )
        mock_hist.assert_not_called()
        self.assertEqual(result, "Top run scorers in IPL 2024 [SQL]")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    @patch("app.ai.query_router.router.answer_playoff_match_question")
    def test_ipl_2026_final_scorecard_uses_sql(
        self, mock_playoff, mock_hist
    ):
        mock_playoff.return_value = "IPL 2026 Final Scorecard [SQL]"
        result = self._route("Give me the IPL 2026 final scorecard.")
        mock_playoff.assert_called_once_with("2026", "final", detail_type="scorecard")
        mock_hist.assert_not_called()
        self.assertEqual(result, "IPL 2026 Final Scorecard [SQL]")

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_season_winner_question")
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    @patch("app.ai.query_router.router.answer_playoff_match_question")
    def test_playoff_stage_scorecard_and_summary_variations_route_correctly(
        self, mock_playoff, mock_hist, mock_winner
    ):
        cases = [
            ("Give me the scorecard of the second qualifier in IPL 2024.", ("2024", "qualifier_2", "scorecard")),
            ("Second qualifier IPL 2024 scorecard", ("2024", "qualifier_2", "scorecard")),
            ("IPL 2024 Qualifier 2", ("2024", "qualifier_2", "summary")),
            ("Who played the second qualifier in IPL 2024?", ("2024", "qualifier_2", "summary")),
            ("Who won the second qualifier in IPL 2024?", ("2024", "qualifier_2", "summary")),
            ("Show the eliminator scorecard in IPL 2024", ("2024", "eliminator", "scorecard")),
            ("Give me IPL 2024 Qualifier 1 scorecard", ("2024", "qualifier_1", "scorecard")),
            ("Show the eliminator scorecard in IPL 2016", ("2016", "eliminator", "scorecard")),
            ("Give me IPL 2023 Qualifier 2 scorecard", ("2023", "qualifier_2", "scorecard")),
            ("Give me IPL 2026 Qualifier 1 scorecard", ("2026", "qualifier_1", "scorecard")),
        ]
        for query, (exp_season, exp_stage, exp_detail) in cases:
            mock_playoff.reset_mock()
            mock_playoff.return_value = f"{exp_season}-{exp_stage}-{exp_detail}"
            res = self._route(query)
            mock_playoff.assert_called_once_with(exp_season, exp_stage, detail_type=exp_detail)
            self.assertEqual(res, f"{exp_season}-{exp_stage}-{exp_detail}")

        mock_hist.assert_not_called()
        mock_winner.assert_not_called()

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    @patch("app.ai.query_router.router.answer_playoff_match_question")
    def test_ambiguous_playoff_queries_ask_for_clarification(self, mock_playoff, mock_hist):
        res_qual = self._route("Give me the IPL 2024 qualifier scorecard.")
        self.assertIn("Qualifier 1 or Qualifier 2", res_qual)

        res_playoff = self._route("Give me the IPL 2024 playoff scorecard.")
        self.assertIn("Qualifier 1, Qualifier 2, Eliminator, or Final", res_playoff)

        res_missing_season = self._route("Give me the Qualifier 2 scorecard.")
        self.assertIn("specify the IPL season", res_missing_season)

        res_multi_season = self._route("IPL 2023 and 2024 Qualifier 2 scorecard.")
        self.assertIn("single season", res_multi_season)

        res_multi_stage = self._route("IPL 2024 Qualifier 1 and Qualifier 2 scorecard.")
        self.assertIn("one playoff stage at a time", res_multi_stage)

        mock_playoff.assert_not_called()
        mock_hist.assert_not_called()

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.resolve_playoff_match")
    def test_missing_playoff_match_record_returns_clear_message_without_llm(
        self, mock_resolve, mock_gen
    ):
        mock_resolve.return_value = {
            "status": "not_found",
            "season": "2007/08",
            "stage": "qualifier_2",
            "stage_label": "Qualifier 2",
            "match": None,
            "matches": [],
        }
        result = self._route("Give me IPL 2008 Qualifier 2 scorecard.")
        mock_resolve.assert_called_once_with("2007/08", "qualifier_2")
        mock_gen.assert_not_called()
        self.assertIn("No Qualifier 2 match record was found", result)

    @patch.dict("os.environ", {"GEMINI_KNOWLEDGE_CUTOFF_SEASON": "2024", "GEMINI_KNOWLEDGE_CUTOFF_DATE": "2025-03-01"})
    @patch("app.ai.query_router.router.answer_playoff_match_question")
    @patch("app.ai.query_router.router.answer_historical_llm_question")
    def test_narrative_playoff_question_still_uses_gemini_historical_within_cutoff(
        self, mock_hist, mock_playoff
    ):
        mock_hist.return_value = "Historical Qualifier 2 narrative"
        result = self._route("Explain IPL 2024 Qualifier 2")
        mock_hist.assert_called_once()
        mock_playoff.assert_not_called()
        self.assertEqual(result, "Historical Qualifier 2 narrative")


if __name__ == "__main__":
    unittest.main()

