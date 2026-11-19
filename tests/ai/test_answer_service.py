"""Tests for the AI answer service functions."""

import unittest
from decimal import Decimal
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Shared mock data factories
# ---------------------------------------------------------------------------

def _batting_row(**kwargs):
    defaults = {
        "player_id": "v-kohli",
        "player_name": "V Kohli",
        "matches_played": 237,
        "innings_batted": 236,
        "total_runs": 7263,
        "highest_score": 113,
        "balls_faced": 5430,
        "dismissals": 212,
        "batting_average": Decimal("34.26"),
        "strike_rate": Decimal("133.75"),
    }
    defaults.update(kwargs)
    return defaults


def _bowling_row(**kwargs):
    defaults = {
        "player_id": "jj-bumrah",
        "player_name": "JJ Bumrah",
        "matches_bowled": 120,
        "innings_bowled": 120,
        "legal_balls": 2520,
        "runs_conceded": 3200,
        "wickets": 145,
        "economy": Decimal("7.62"),
        "bowling_average": Decimal("22.07"),
        "bowling_strike_rate": Decimal("17.38"),
    }
    defaults.update(kwargs)
    return defaults


def _team_stats(**kwargs):
    defaults = {
        "team_id": 1,
        "team_name": "Mumbai Indians",
        "short_code": "MI",
        "is_active": True,
        "matches_played": 243,
        "wins": 143,
        "losses": 97,
        "ties": 1,
        "no_results": 2,
        "win_percentage": Decimal("58.85"),
        "innings_batted": 243,
        "runs_scored": 46000,
        "wickets_lost": 1800,
        "legal_balls_faced": 86580,
        "batting_run_rate": Decimal("8.49"),
        "innings_bowled": 243,
        "runs_conceded": 44500,
        "wickets_taken": 1900,
        "legal_balls_bowled": 86580,
        "bowling_economy": Decimal("7.90"),
        "championship_titles": 5,
        "championship_seasons": ["2013", "2015", "2017", "2019", "2020/21"],
    }
    defaults.update(kwargs)
    return defaults


def _h2h_row(**kwargs):
    defaults = {
        "team_one": "Chennai Super Kings",
        "team_two": "Mumbai Indians",
        "matches_played": 36,
        "team_one_wins": 20,
        "team_two_wins": 16,
        "ties": 0,
        "no_results": 0,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestAnswerMatchQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_result")
    def test_valid_match_calls_llm(self, mock_get, mock_gen):
        mock_get.return_value = {
            "match_id": 335982,
            "season": "2007/08",
            "match_date": "2008-04-18",
            "winner": "Kolkata Knight Riders",
            "result_type": "wickets",
            "win_by_runs": 0,
            "win_by_wickets": 140,
            "result_method": None,
        }
        mock_gen.return_value = "KKR won by wickets."

        from app.ai.answer_service import answer_match_question
        result = answer_match_question(335982, "Who won match 335982?")

        mock_get.assert_called_once_with(335982)
        mock_gen.assert_called_once()
        self.assertEqual(result, "KKR won by wickets.")

    @patch("app.ai.answer_service.get_match_result")
    def test_missing_match_returns_no_record_message(self, mock_get):
        mock_get.return_value = None
        from app.ai.answer_service import answer_match_question
        result = answer_match_question(999999, "Who won?")
        self.assertIn("No database record", result)
        self.assertIn("999999", result)


class TestAnswerSeasonWinnerQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.get_season_winner")
    def test_valid_season_returns_winner(self, mock_get):
        mock_get.return_value = {
            "winner": "Mumbai Indians",
            "match_id": 11111,
            "match_date": "2019-05-12",
        }
        from app.ai.answer_service import answer_season_winner_question
        result = answer_season_winner_question("2019")
        self.assertIn("Mumbai Indians", result)

    @patch("app.ai.answer_service.get_season_winner")
    def test_missing_season_returns_not_found(self, mock_get):
        mock_get.return_value = None
        from app.ai.answer_service import answer_season_winner_question
        result = answer_season_winner_question("2099")
        self.assertIn("2099", result)
        self.assertIn("no ipl final match record was found", result.lower())


class TestAnswerLeaderboardQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.get_batting_leaderboard")
    def test_batting_runs_leaderboard(self, mock_get):
        mock_get.return_value = [
            {
                "player_name": "V Kohli",
                "total_runs": 7263,
                "matches_played": 237,
            }
        ]
        from app.ai.answer_service import answer_leaderboard_question
        result = answer_leaderboard_question(
            category="runs",
            question_type="batting",
            season=None,
            limit=10,
        )
        self.assertIn("V Kohli", result)
        self.assertIn("7263", result)

    @patch("app.ai.answer_service.get_bowling_leaderboard")
    def test_bowling_wickets_leaderboard(self, mock_get):
        mock_get.return_value = [
            {
                "player_name": "JJ Bumrah",
                "wickets": 145,
                "matches_played": 120,
            }
        ]
        from app.ai.answer_service import answer_leaderboard_question
        result = answer_leaderboard_question(
            category="wickets",
            question_type="bowling",
            season=None,
            limit=10,
        )
        self.assertIn("JJ Bumrah", result)

    @patch("app.ai.answer_service.get_batting_leaderboard")
    def test_empty_leaderboard_returns_no_records(self, mock_get):
        mock_get.return_value = []
        from app.ai.answer_service import answer_leaderboard_question
        result = answer_leaderboard_question(
            category="runs",
            question_type="batting",
            season="2099",
            limit=10,
        )
        self.assertIn("No leaderboard records", result)


class TestAnswerPlayerQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.get_player_bowling_stats")
    @patch("app.ai.answer_service.get_player_batting_stats")
    def test_valid_player_formats_stats(self, mock_bat, mock_bowl):
        mock_bat.return_value = [_batting_row()]
        mock_bowl.return_value = [_bowling_row(player_name="V Kohli")]
        from app.ai.answer_service import answer_player_question
        result = answer_player_question("V Kohli")
        self.assertIn("V Kohli", result)
        self.assertIn("7263", result)
        self.assertIn("Supabase", result)

    @patch("app.ai.answer_service.get_player_bowling_stats")
    @patch("app.ai.answer_service.get_player_batting_stats")
    def test_no_results_returns_not_found(self, mock_bat, mock_bowl):
        mock_bat.return_value = []
        mock_bowl.return_value = []
        from app.ai.answer_service import answer_player_question
        result = answer_player_question("Unknown Player XYZZY")
        self.assertIn("No IPL statistics found", result)

    def test_empty_name_returns_please_provide(self):
        from app.ai.answer_service import answer_player_question
        result = answer_player_question("")
        self.assertIn("Please provide", result)

    @patch("app.ai.answer_service.get_player_bowling_stats")
    @patch("app.ai.answer_service.get_player_batting_stats")
    def test_batting_only_player_formats_no_bowling(self, mock_bat, mock_bowl):
        mock_bat.return_value = [_batting_row()]
        mock_bowl.return_value = []
        from app.ai.answer_service import answer_player_question
        result = answer_player_question("V Kohli")
        self.assertIn("No bowling records", result)
        self.assertIn("7263", result)

    @patch("app.ai.answer_service.get_player_bowling_stats")
    @patch("app.ai.answer_service.get_player_batting_stats")
    def test_mismatched_player_ids_not_paired(self, mock_bat, mock_bowl):
        mock_bat.return_value = [_batting_row(player_id="p1", player_name="RG Sharma")]
        mock_bowl.return_value = [_bowling_row(player_id="p2", player_name="MM Sharma", wickets=99)]
        from app.ai.answer_service import answer_player_question
        result = answer_player_question("Sharma")
        self.assertIn("RG Sharma", result)
        self.assertIn("No bowling records", result)
        self.assertNotIn("99", result)


class TestAnswerTeamQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.get_individual_team_statistics")
    def test_valid_team_formats_stats(self, mock_get):
        mock_get.return_value = _team_stats()
        from app.ai.answer_service import answer_team_question
        result = answer_team_question("Mumbai Indians")
        self.assertIn("Mumbai Indians", result)
        self.assertIn("143", result)   # wins
        self.assertIn("Supabase", result)

    @patch("app.ai.answer_service.get_individual_team_statistics")
    def test_missing_team_returns_not_found(self, mock_get):
        mock_get.return_value = None
        from app.ai.answer_service import answer_team_question
        result = answer_team_question("Unknown Team XYZZY")
        self.assertIn("No IPL statistics found", result)

    @patch("app.ai.answer_service.get_individual_team_statistics")
    def test_ambiguous_team_raises_value_error(self, mock_get):
        mock_get.side_effect = ValueError("Ambiguous team 'Super'. Matches: ...")
        from app.ai.answer_service import answer_team_question
        result = answer_team_question("Super")
        self.assertIn("Team lookup error", result)

    def test_empty_identifier_returns_please_provide(self):
        from app.ai.answer_service import answer_team_question
        result = answer_team_question("")
        self.assertIn("Please provide", result)

    @patch("app.ai.answer_service.get_individual_team_statistics")
    def test_championship_titles_shown(self, mock_get):
        mock_get.return_value = _team_stats()
        from app.ai.answer_service import answer_team_question
        result = answer_team_question("MI")
        self.assertIn("5", result)
        self.assertIn("2013", result)


class TestAnswerHeadToHeadQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.get_team_head_to_head")
    def test_valid_h2h_formats_result(self, mock_get):
        mock_get.return_value = _h2h_row()
        from app.ai.answer_service import answer_head_to_head_question
        result = answer_head_to_head_question("CSK", "MI")
        self.assertIn("Chennai Super Kings", result)
        self.assertIn("Mumbai Indians", result)
        self.assertIn("36", result)
        self.assertIn("Supabase", result)

    @patch("app.ai.answer_service.get_team_head_to_head")
    def test_no_h2h_records_returns_not_found(self, mock_get):
        mock_get.return_value = None
        from app.ai.answer_service import answer_head_to_head_question
        result = answer_head_to_head_question("CSK", "Unknown")
        self.assertIn("No head-to-head records", result)

    @patch("app.ai.answer_service.get_team_head_to_head")
    def test_value_error_returns_lookup_error(self, mock_get):
        mock_get.side_effect = ValueError("Same team provided twice.")
        from app.ai.answer_service import answer_head_to_head_question
        result = answer_head_to_head_question("MI", "MI")
        self.assertIn("Head-to-head lookup error", result)

    def test_empty_teams_returns_please_provide(self):
        from app.ai.answer_service import answer_head_to_head_question
        result = answer_head_to_head_question("", "MI")
        self.assertIn("Please provide", result)


class TestAnswerTeamVersusMatchesQuestion(unittest.TestCase):

    @patch("app.ai.answer_service.get_team_versus_matches")
    def test_multiple_matches_in_season_all_returned(self, mock_get):
        mock_get.return_value = {
            "team_one": "Chennai Super Kings",
            "team_two": "Mumbai Indians",
            "season": "2023",
            "matches": [
                {
                    "match_id": 1359486,
                    "season": "2023",
                    "match_date": "2023-04-08",
                    "teams": "Mumbai Indians vs Chennai Super Kings",
                    "venue": "Wankhede Stadium",
                    "city": "Mumbai",
                    "winner": "Chennai Super Kings",
                    "victory_margin": "7 wickets",
                    "is_super_over": False,
                    "result_summary": "Chennai Super Kings won by 7 wickets",
                },
                {
                    "match_id": 1359523,
                    "season": "2023",
                    "match_date": "2023-05-06",
                    "teams": "Mumbai Indians vs Chennai Super Kings",
                    "venue": "MA Chidambaram Stadium",
                    "city": "Chennai",
                    "winner": "Chennai Super Kings",
                    "victory_margin": "6 wickets",
                    "is_super_over": False,
                    "result_summary": "Chennai Super Kings won by 6 wickets",
                },
            ],
        }
        from app.ai.answer_service import answer_team_versus_matches_question
        result = answer_team_versus_matches_question("CSK", "MI", season="2023")
        mock_get.assert_called_once_with("CSK", "MI", season="2023")
        self.assertIn("Matches found: **2**", result)
        self.assertIn("2023-04-08", result)
        self.assertIn("2023-05-06", result)
        self.assertIn("Wankhede Stadium", result)
        self.assertIn("MA Chidambaram Stadium", result)
        self.assertIn("7 wickets", result)
        self.assertIn("6 wickets", result)

    @patch("app.ai.answer_service.get_team_versus_matches")
    def test_no_matches_in_season_message(self, mock_get):
        mock_get.return_value = {
            "team_one": "Chennai Super Kings",
            "team_two": "Mumbai Indians",
            "season": "2099",
            "matches": [],
        }
        from app.ai.answer_service import answer_team_versus_matches_question
        result = answer_team_versus_matches_question("CSK", "MI", season="2099")
        self.assertIn("No IPL 2099 matches found", result)

    @patch("app.ai.answer_service.get_team_versus_matches")
    def test_invalid_team_returns_lookup_error(self, mock_get):
        mock_get.side_effect = ValueError("Team 'FakeTeam' was not found.")
        from app.ai.answer_service import answer_team_versus_matches_question
        result = answer_team_versus_matches_question("FakeTeam", "MI", season="2024")
        self.assertIn("Match lookup error", result)
        self.assertIn("FakeTeam", result)


class TestLLMClientPlaceholderDetection(unittest.TestCase):
    """Unit tests for placeholder-model detection in llm/client.py."""

    def test_is_placeholder_your_underscore(self):
        from app.ai.llm.client import _is_placeholder
        self.assertTrue(_is_placeholder("your_supported_mistral_model"))

    def test_is_placeholder_your_hyphen(self):
        from app.ai.llm.client import _is_placeholder
        self.assertTrue(_is_placeholder("your-gemini-api-key"))

    def test_is_placeholder_angle_bracket(self):
        from app.ai.llm.client import _is_placeholder
        self.assertTrue(_is_placeholder("<your-key>"))

    def test_real_model_not_placeholder(self):
        from app.ai.llm.client import _is_placeholder
        self.assertFalse(_is_placeholder("gemini-1.5-flash"))
        self.assertFalse(_is_placeholder("llama-3.1-70b-versatile"))

    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "your-placeholder-key",
        "GEMINI_MODEL": "gemini-1.5-flash",
    })
    def test_gemini_placeholder_key_raises_runtime_error(self):
        from app.ai.llm.client import _generate_gemini
        with self.assertRaises(RuntimeError) as ctx:
            _generate_gemini("test prompt")
        self.assertIn("placeholder", str(ctx.exception).lower())

    @patch.dict("os.environ", {
        "GROQ_API_KEY": "valid-key",
        "GROQ_MODEL": "your_supported_groq_model",
    })
    def test_openai_compatible_placeholder_model_raises(self):
        from app.ai.llm.client import _generate_openai_compatible
        with self.assertRaises(RuntimeError) as ctx:
            _generate_openai_compatible("groq", "test prompt")
        self.assertIn("placeholder", str(ctx.exception).lower())

    @patch.dict("os.environ", {
        "AI_PRIMARY_PROVIDER": "gemini",
        "AI_PROVIDER_ORDER": "gemini,groq,mistral",
    })
    @patch("app.ai.llm.client._generate_with_provider")
    def test_generate_response_falls_back_when_primary_fails(self, mock_gen):
        mock_gen.side_effect = [
            RuntimeError("Gemini rate limit"),
            "Response from Groq",
        ]
        from app.ai.llm.client import generate_response
        result = generate_response("Who won match 335982?")
        self.assertEqual(result, "Response from Groq")
        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(mock_gen.call_args_list[0].args[0], "gemini")
        self.assertEqual(mock_gen.call_args_list[1].args[0], "groq")

    @patch.dict("os.environ", {
        "AI_PRIMARY_PROVIDER": "gemini",
        "AI_PROVIDER_ORDER": "gemini,groq",
    })
    @patch("app.ai.llm.client._generate_with_provider")
    def test_generate_response_raises_when_all_fail(self, mock_gen):
        mock_gen.side_effect = RuntimeError("Provider down")
        from app.ai.llm.client import generate_response
        with self.assertRaises(RuntimeError) as ctx:
            generate_response("Who won?")
        self.assertIn("gemini, groq", str(ctx.exception))

    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "AIzaTestKey123",
        "GEMINI_MODEL": "gemini-2.5-flash",
        "AI_TIMEOUT": "15",
    })
    @patch("app.ai.llm.client.genai.Client")
    def test_generate_gemini_applies_ai_timeout_in_milliseconds(self, mock_client_cls):
        fake_client = mock_client_cls.return_value.__enter__.return_value
        fake_resp = unittest.mock.MagicMock()
        fake_resp.text = "Gemini answer"
        fake_client.models.generate_content.return_value = fake_resp

        from app.ai.llm.client import _generate_gemini
        result = _generate_gemini("Who won IPL 2024?")

        self.assertEqual(result, "Gemini answer")
        http_opts = mock_client_cls.call_args.kwargs["http_options"]
        self.assertEqual(http_opts.timeout, 15000)

    @patch.dict("os.environ", {
        "AI_PRIMARY_PROVIDER": "gemini",
        "AI_PROVIDER_ORDER": "gemini,groq",
        "GEMINI_API_KEY": "super-secret-gemini-key",
        "GROQ_API_KEY": "super-secret-groq-key",
    })
    @patch("app.ai.llm.client._generate_with_provider")
    def test_generate_response_sanitizes_secrets_in_warning_logs(self, mock_gen):
        mock_gen.side_effect = [
            RuntimeError("Failed with Bearer super-secret-gemini-key"),
            "Groq fallback succeeded",
        ]
        from app.ai.llm.client import generate_response
        with self.assertLogs("app.ai.llm.client", level="WARNING") as cm:
            res = generate_response("Test prompt")
        self.assertEqual(res, "Groq fallback succeeded")
        joined_logs = "\n".join(cm.output)
        self.assertNotIn("super-secret-gemini-key", joined_logs)
        self.assertIn("[REDACTED]", joined_logs)


class TestCutoffAwareAnswerServices(unittest.TestCase):
    """Tests for within-cutoff Gemini, post-cutoff overview, and cross-cutoff synthesis."""

    @patch("app.ai.answer_service.hybrid_retrieve")
    @patch("app.ai.answer_service.generate_response")
    def test_historical_llm_question_calls_gemini_directly_without_rag(self, mock_gen, mock_ret):
        mock_gen.return_value = "Rajasthan Royals won IPL 2008 under Shane Warne."
        from app.ai.answer_service import answer_historical_llm_question
        result = answer_historical_llm_question(
            "Explain Rajasthan Royals' 2008 campaign.",
            seasons=["2007/08"],
            team_identifier="rajasthan royals",
        )
        mock_gen.assert_called_once()
        mock_ret.assert_not_called()
        self.assertIn("Shane Warne", result)
        self.assertIn("Gemini Historical Knowledge", result)

    @patch("app.ai.answer_service.answer_rag_question")
    @patch("app.ai.answer_service.get_team_runs_leaderboard", return_value=[])
    @patch("app.ai.answer_service.get_bowling_leaderboard", return_value=[])
    @patch("app.ai.answer_service.get_batting_leaderboard")
    @patch("app.ai.answer_service.get_season_winner")
    @patch("app.ai.answer_service.get_latest_season", return_value="2026")
    def test_post_cutoff_overview_uses_sql_plus_rag_for_latest_season(
        self, mock_latest, mock_win, mock_bat, mock_bowl, mock_team_lb, mock_rag
    ):
        mock_win.return_value = {"winner": "Royal Challengers Bengaluru", "match_id": 1500001, "match_date": "2026-05-31"}
        mock_bat.return_value = [{"player_name": "V Kohli", "total_runs": 650, "matches_played": 14}]
        mock_rag.return_value = "IPL 2026 summary [SQL] [S1]"
        from app.ai.answer_service import answer_post_cutoff_overview_question
        result = answer_post_cutoff_overview_question("What happened in the latest IPL season?")
        mock_latest.assert_called_once()
        mock_rag.assert_called_once()
        self.assertEqual(mock_rag.call_args.kwargs["season"], "2026")
        self.assertIn("Royal Challengers Bengaluru", mock_rag.call_args.kwargs["sql_context"])
        self.assertEqual(result, "IPL 2026 summary [SQL] [S1]")

    @patch("app.ai.answer_service.get_latest_season", return_value=None)
    def test_post_cutoff_overview_missing_latest_season_reports_unavailability(self, mock_latest):
        from app.ai.answer_service import answer_post_cutoff_overview_question
        result = answer_post_cutoff_overview_question("What happened in the latest IPL season?")
        self.assertIn("no recent ipl season records", result.lower())

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.hybrid_retrieve")
    @patch("app.ai.answer_service.get_player_bowling_stats", return_value=[])
    @patch("app.ai.answer_service.get_player_batting_stats")
    def test_player_multi_season_cross_cutoff_combines_sql_and_rag(
        self, mock_bat, mock_bowl, mock_ret, mock_gen
    ):
        mock_bat.side_effect = [
            [_batting_row(total_runs=639, matches_played=14)],
            [_batting_row(total_runs=610, matches_played=15)],
        ]
        mock_ret.return_value = [{
            "chunk_id": 10,
            "title": "IPL 2026 Match Report",
            "season": "2026",
            "source_key": "db:match:1500001",
            "source_path": "supabase://matches/1500001",
            "chunk_text": "Kohli anchored chases in 2026.",
            "hybrid_score": 0.72,
        }]
        mock_gen.return_value = "In 2023 Kohli scored 639 runs [SQL] and in 2026 scored 610 runs [SQL][S1]."

        from app.ai.answer_service import answer_player_multi_season_comparison_question
        result = answer_player_multi_season_comparison_question(
            "Compare Kohli's performance in 2023 and 2026.",
            "Kohli",
            ["2023", "2026"],
            cutoff_info={"scope": "cross_cutoff", "post_seasons": ["2026"], "within_seasons": ["2023"]},
        )
        self.assertEqual(mock_bat.call_count, 2)
        self.assertIn("639", mock_gen.call_args.args[0])
        self.assertIn("610", mock_gen.call_args.args[0])
        self.assertIn("### Sources", result)
        self.assertIn("[SQL]", result)
        self.assertIn("Gemini Historical Knowledge", result)
        self.assertIn("[S1]", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.hybrid_retrieve", return_value=[])
    @patch("app.ai.answer_service.get_bowling_leaderboard", return_value=[])
    @patch("app.ai.answer_service.get_batting_leaderboard", return_value=[])
    @patch("app.ai.answer_service.get_season_winner")
    def test_cross_boundary_season_comparison_distinguishes_sources(
        self, mock_win, mock_bat, mock_bowl, mock_ret, mock_gen
    ):
        mock_win.side_effect = [
            {"winner": "Sunrisers Hyderabad", "match_id": 981019, "match_date": "2016-05-29"},
            {"winner": "Royal Challengers Bengaluru", "match_id": 1500001, "match_date": "2026-05-31"},
        ]
        mock_gen.return_value = "SRH won 2016 [Gemini Historical Knowledge][SQL], whereas RCB won 2026 [SQL]."

        from app.ai.answer_service import answer_cross_boundary_question
        result = answer_cross_boundary_question(
            "Compare IPL 2016 and IPL 2026.",
            seasons=["2016", "2026"],
            cutoff_info={"scope": "cross_cutoff", "within_seasons": ["2016"], "post_seasons": ["2026"]},
        )
        self.assertIn("Gemini Historical Knowledge", result)
        self.assertIn("[SQL]", result)
        self.assertIn("2016", result)


class TestScorecardFormattingAndSeasonFinal(unittest.TestCase):

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_wickets")
    @patch("app.ai.answer_service.get_match_scorecard")
    def test_answer_scorecard_question_formats_full_scorecard_and_fow(
        self, mock_sc, mock_wk, mock_gen
    ):
        mock_sc.return_value = {
            "match": {
                "match_id": 1426312,
                "season": "2024",
                "stage": "Final",
                "match_date": "2024-05-26",
                "venue": "MA Chidambaram Stadium",
                "city": "Chennai",
                "teams": [
                    {"team_name": "Sunrisers Hyderabad"},
                    {"team_name": "Kolkata Knight Riders"},
                ],
                "toss": {"toss_winner_name": "Sunrisers Hyderabad", "toss_decision": "bat"},
                "result": {"summary": "Kolkata Knight Riders won by 8 wickets"},
            },
            "has_super_over": False,
            "innings": [
                {
                    "innings_number": 1,
                    "batting_team": "Sunrisers Hyderabad",
                    "total_runs": 113,
                    "total_wickets": 10,
                    "overs": "18.3",
                    "run_rate": "6.11",
                    "batting": [
                        {
                            "player_name": "PJ Cummins",
                            "dismissal": "c Starc b Russell",
                            "runs": 24,
                            "balls": 19,
                            "fours": 2,
                            "sixes": 1,
                            "strike_rate": "126.32",
                        }
                    ],
                    "bowling": [
                        {
                            "player_name": "MA Starc",
                            "overs": "3.0",
                            "maidens": 0,
                            "runs_conceded": 14,
                            "wickets": 2,
                            "economy": "4.67",
                        }
                    ],
                    "extras": {
                        "total_extras": 13,
                        "wides": 6,
                        "no_balls": 0,
                        "byes": 4,
                        "leg_byes": 3,
                        "penalty": 0,
                    },
                },
                {
                    "innings_number": 2,
                    "batting_team": "Kolkata Knight Riders",
                    "total_runs": 114,
                    "total_wickets": 2,
                    "overs": "10.3",
                    "run_rate": "10.86",
                    "batting": [
                        {
                            "player_name": "VR Iyer",
                            "dismissal": "not out",
                            "runs": 52,
                            "balls": 26,
                            "fours": 4,
                            "sixes": 3,
                            "strike_rate": "200.00",
                        }
                    ],
                    "bowling": [
                        {
                            "player_name": "PJ Cummins",
                            "overs": "2.0",
                            "maidens": 0,
                            "runs_conceded": 18,
                            "wickets": 1,
                            "economy": "9.00",
                        }
                    ],
                    "extras": {
                        "total_extras": 8,
                        "wides": 5,
                        "no_balls": 1,
                        "byes": 0,
                        "leg_byes": 2,
                        "penalty": 0,
                    },
                },
            ],
            "super_overs": [],
        }
        mock_wk.return_value = {
            "match_id": 1426312,
            "has_super_over": False,
            "innings": [
                {
                    "innings_number": 1,
                    "fall_of_wickets": [
                        {"wicket_number": 1, "score": 2, "player_name": "Abhishek Sharma", "overs": "0.5"}
                    ],
                },
                {
                    "innings_number": 2,
                    "fall_of_wickets": [
                        {"wicket_number": 1, "score": 11, "player_name": "SP Narine", "overs": "1.2"}
                    ],
                },
            ],
            "super_overs": [],
        }

        from app.ai.answer_service import answer_scorecard_question
        result = answer_scorecard_question(1426312)

        mock_gen.assert_not_called()
        self.assertIn("IPL 2024 Final Match 1426312 - Scorecard", result)
        self.assertIn("**Fixture:** Sunrisers Hyderabad vs Kolkata Knight Riders", result)
        self.assertIn("**Result:** Kolkata Knight Riders won by 8 wickets", result)
        self.assertIn("Innings 1 - Sunrisers Hyderabad", result)
        self.assertIn("Innings 2 - Kolkata Knight Riders", result)
        self.assertIn("**Extras:** 13", result)
        self.assertIn("**Fall of wickets:** 1-2 (Abhishek Sharma, 0.5 ov)", result)
        self.assertIn("**Fall of wickets:** 1-11 (SP Narine, 1.2 ov)", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_scorecard", return_value=None)
    def test_answer_scorecard_question_returns_clear_sql_error_when_missing(
        self, _mock_sc, mock_gen
    ):
        from app.ai.answer_service import answer_scorecard_question
        result = answer_scorecard_question(999999)
        mock_gen.assert_not_called()
        self.assertEqual(result, "No scorecard found for match 999999.")

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.answer_scorecard_question", return_value="## IPL 2024 Final Match 1426312 - Scorecard")
    @patch("app.ai.answer_service.get_season_winner")
    def test_answer_season_final_detail_resolves_match_id_via_sql(
        self, mock_winner, mock_sc_answer, mock_gen
    ):
        mock_winner.return_value = {"season": "2024", "match_id": 1426312, "stage": "Final"}
        from app.ai.answer_service import answer_season_final_detail_question
        result = answer_season_final_detail_question("2024", detail_type="scorecard")
        mock_winner.assert_called_once_with("2024")
        mock_sc_answer.assert_called_once_with(1426312)
        mock_gen.assert_not_called()
        self.assertIn("1426312", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_season_winner", return_value=None)
    def test_answer_season_final_detail_returns_error_when_final_missing(
        self, _mock_winner, mock_gen
    ):
        from app.ai.answer_service import answer_season_final_detail_question
        result = answer_season_final_detail_question("2099", detail_type="scorecard")
        mock_gen.assert_not_called()
        self.assertEqual(result, "No IPL final match record was found in the database for season 2099.")

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_season_winner")
    @patch("app.ai.answer_service.answer_scorecard_question", return_value="## IPL 2024 Qualifier 2 Match 1426311 - Scorecard")
    @patch("app.ai.answer_service.resolve_playoff_match")
    def test_answer_playoff_match_question_resolves_qualifier_2_scorecard_without_season_winner(
        self, mock_resolve, mock_sc, mock_winner, mock_gen
    ):
        mock_resolve.return_value = {
            "status": "resolved",
            "season": "2024",
            "stage": "qualifier_2",
            "stage_label": "Qualifier 2",
            "match": {"match_id": 1426311, "stage": "Qualifier 2"},
            "matches": [{"match_id": 1426311, "stage": "Qualifier 2"}],
        }
        from app.ai.answer_service import answer_playoff_match_question
        result = answer_playoff_match_question("2024", "qualifier_2", detail_type="scorecard")
        mock_resolve.assert_called_once_with("2024", "qualifier_2")
        mock_sc.assert_called_once_with(1426311)
        mock_winner.assert_not_called()
        mock_gen.assert_not_called()
        self.assertIn("1426311", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_details")
    @patch("app.ai.answer_service.resolve_playoff_match")
    def test_answer_playoff_match_question_formats_summary_via_sql(
        self, mock_resolve, mock_details, mock_gen
    ):
        mock_resolve.return_value = {
            "status": "resolved",
            "season": "2024",
            "stage": "qualifier_2",
            "stage_label": "Qualifier 2",
            "match": {"match_id": 1426311, "stage": "Qualifier 2"},
            "matches": [{"match_id": 1426311, "stage": "Qualifier 2"}],
        }
        mock_details.return_value = {
            "match_id": 1426311,
            "season": "2024",
            "match_date": "2024-05-24",
            "venue": "MA Chidambaram Stadium",
            "city": "Chennai",
            "stage": "Qualifier 2",
            "teams": [
                {"team_name": "Sunrisers Hyderabad"},
                {"team_name": "Rajasthan Royals"},
            ],
            "toss": {"toss_winner_name": "Rajasthan Royals", "toss_decision": "field"},
            "result": {"summary": "Sunrisers Hyderabad won by 36 runs"},
        }
        from app.ai.answer_service import answer_playoff_match_question
        result = answer_playoff_match_question("2024", "qualifier_2", detail_type="summary")
        mock_details.assert_called_once_with(1426311)
        mock_gen.assert_not_called()
        self.assertIn("IPL 2024 Qualifier 2 (Match 1426311)", result)
        self.assertIn("**Fixture:** Sunrisers Hyderabad vs Rajasthan Royals", result)
        self.assertIn("**Result:** Sunrisers Hyderabad won by 36 runs", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.resolve_playoff_match")
    def test_answer_playoff_match_question_handles_not_found_and_ambiguous(
        self, mock_resolve, mock_gen
    ):
        from app.ai.answer_service import answer_playoff_match_question

        mock_resolve.return_value = {
            "status": "not_found",
            "season": "2007/08",
            "stage": "qualifier_2",
            "stage_label": "Qualifier 2",
            "match": None,
            "matches": [],
        }
        missing_res = answer_playoff_match_question("2007/08", "qualifier_2", detail_type="scorecard")
        self.assertIn("No Qualifier 2 match record was found", missing_res)

        mock_resolve.return_value = {
            "status": "ambiguous",
            "season": "2024",
            "stage": "qualifier_2",
            "stage_label": "Qualifier 2",
            "match": None,
            "matches": [
                {"match_id": 1001, "match_date": "2024-05-23"},
                {"match_id": 1002, "match_date": "2024-05-24"},
            ],
        }
        ambig_res = answer_playoff_match_question("2024", "qualifier_2", detail_type="scorecard")
        self.assertIn("Multiple Qualifier 2 records", ambig_res)
        self.assertIn("1001", ambig_res)
        mock_gen.assert_not_called()

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_scorecard")
    @patch("app.ai.answer_service.get_match_details")
    @patch("app.ai.answer_service.get_match_awards")
    def test_potm_ipl_final_formats_player_name_first_with_details_and_stats(
        self, mock_awards, mock_details, mock_scorecard, mock_gen
    ):
        mock_awards.return_value = [
            {
                "match_id": 1426312,
                "season": "2024",
                "match_date": "2024-05-26",
                "stage": "Final",
                "award_name": "Player of the Match",
                "player_id": "3fb19989",
                "player_name": "MA Starc",
                "player_team": "Kolkata Knight Riders",
                "teams": "Sunrisers Hyderabad vs Kolkata Knight Riders",
            }
        ]
        mock_details.return_value = {
            "match_id": 1426312,
            "season": "2024",
            "match_date": "2024-05-26",
            "venue": "MA Chidambaram Stadium",
            "city": "Chennai",
            "stage": "Final",
            "teams": [
                {"team_name": "Sunrisers Hyderabad"},
                {"team_name": "Kolkata Knight Riders"},
            ],
            "result": {"summary": "Kolkata Knight Riders won by 8 wickets"},
        }
        mock_scorecard.return_value = {
            "innings": [
                {
                    "batting": [],
                    "bowling": [
                        {
                            "player_id": "3fb19989",
                            "player_name": "MA Starc",
                            "overs": "3.0",
                            "legal_balls": 18,
                            "runs_conceded": 14,
                            "wickets": 2,
                            "economy": 4.67,
                        }
                    ],
                }
            ],
            "super_overs": [],
        }

        from app.ai.answer_service import answer_match_awards_question

        result = answer_match_awards_question(season="2024", final_only=True)
        mock_gen.assert_not_called()

        lines = result.splitlines()
        self.assertTrue(lines[0].startswith("🏆 Player of the Match:"))
        self.assertIn("MA Starc", lines[0])
        # Player name appears before all match details
        self.assertLess(result.index("MA Starc"), result.index("**IPL 2024 Final**"))
        self.assertLess(result.index("MA Starc"), result.index("- Match: Sunrisers Hyderabad vs Kolkata Knight Riders"))
        self.assertIn("- Date: 26 May 2024", result)
        self.assertIn("- Result: Kolkata Knight Riders won by 8 wickets", result)
        self.assertIn("- Match ID: 1426312", result)
        self.assertIn("- Team: Kolkata Knight Riders", result)
        self.assertIn("- Performance: Bowling: 2/14 (3.0 overs, econ 4.67)", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_scorecard")
    @patch("app.ai.answer_service.get_match_details")
    @patch("app.ai.answer_service.get_match_awards")
    @patch("app.ai.answer_service.resolve_playoff_match")
    def test_potm_qualifier_2_formats_player_name_first_with_bat_and_bowl_stats(
        self, mock_resolve, mock_awards, mock_details, mock_scorecard, mock_gen
    ):
        mock_resolve.return_value = {
            "status": "resolved",
            "season": "2024",
            "stage": "qualifier_2",
            "stage_label": "Qualifier 2",
            "match": {"match_id": 1426311, "stage": "Qualifier 2"},
            "matches": [{"match_id": 1426311, "stage": "Qualifier 2"}],
        }
        mock_awards.return_value = [
            {
                "match_id": 1426311,
                "season": "2024",
                "match_date": "2024-05-24",
                "stage": "Qualifier 2",
                "award_name": "Player of the Match",
                "player_id": "f9e6e7ef",
                "player_name": "Shahbaz Ahmed",
                "player_team": "Sunrisers Hyderabad",
                "teams": "Sunrisers Hyderabad vs Rajasthan Royals",
            }
        ]
        mock_details.return_value = {
            "match_id": 1426311,
            "season": "2024",
            "match_date": "2024-05-24",
            "venue": "MA Chidambaram Stadium",
            "city": "Chennai",
            "stage": "Qualifier 2",
            "teams": [
                {"team_name": "Sunrisers Hyderabad"},
                {"team_name": "Rajasthan Royals"},
            ],
            "result": {"summary": "Sunrisers Hyderabad won by 36 runs"},
        }
        mock_scorecard.return_value = {
            "innings": [
                {
                    "batting": [
                        {
                            "player_id": "f9e6e7ef",
                            "player_name": "Shahbaz Ahmed",
                            "runs": 18,
                            "balls": 18,
                            "fours": 0,
                            "sixes": 1,
                            "is_out": True,
                        }
                    ],
                    "bowling": [],
                },
                {
                    "batting": [],
                    "bowling": [
                        {
                            "player_id": "f9e6e7ef",
                            "player_name": "Shahbaz Ahmed",
                            "overs": "4.0",
                            "legal_balls": 24,
                            "runs_conceded": 23,
                            "wickets": 3,
                            "economy": 5.75,
                        }
                    ],
                },
            ],
            "super_overs": [],
        }

        from app.ai.answer_service import answer_playoff_match_question

        result = answer_playoff_match_question("2024", "qualifier_2", detail_type="potm")
        mock_gen.assert_not_called()

        lines = result.splitlines()
        self.assertTrue(lines[0].startswith("🏆 Player of the Match:"))
        self.assertIn("Shahbaz Ahmed", lines[0])
        self.assertLess(result.index("Shahbaz Ahmed"), result.index("**IPL 2024 Qualifier 2**"))
        self.assertIn("- Match: Sunrisers Hyderabad vs Rajasthan Royals", result)
        self.assertIn("- Date: 24 May 2024", result)
        self.assertIn("- Result: Sunrisers Hyderabad won by 36 runs", result)
        self.assertIn("- Match ID: 1426311", result)
        self.assertIn("- Team: Sunrisers Hyderabad", result)
        self.assertIn("Batting: 18 (18 balls, 1x6)", result)
        self.assertIn("Bowling: 3/23 (4.0 overs, econ 5.75)", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_scorecard")
    @patch("app.ai.answer_service.get_match_details")
    @patch("app.ai.answer_service.get_match_awards")
    def test_potm_league_match_formats_player_name_first(
        self, mock_awards, mock_details, mock_scorecard, mock_gen
    ):
        mock_awards.return_value = [
            {
                "match_id": 335982,
                "season": "2007/08",
                "match_date": "2008-04-18",
                "stage": None,
                "award_name": "Player of the Match",
                "player_id": "b8a55852",
                "player_name": "BB McCullum",
                "player_team": "Kolkata Knight Riders",
                "teams": "Royal Challengers Bengaluru vs Kolkata Knight Riders",
            }
        ]
        mock_details.return_value = {
            "match_id": 335982,
            "season": "2007/08",
            "match_date": "2008-04-18",
            "venue": "M Chinnaswamy Stadium",
            "city": "Bengaluru",
            "stage": None,
            "teams": [
                {"team_name": "Royal Challengers Bengaluru"},
                {"team_name": "Kolkata Knight Riders"},
            ],
            "result": {"summary": "Kolkata Knight Riders won by 140 runs"},
        }
        mock_scorecard.return_value = {
            "innings": [
                {
                    "batting": [
                        {
                            "player_id": "b8a55852",
                            "player_name": "BB McCullum",
                            "runs": 158,
                            "balls": 73,
                            "fours": 10,
                            "sixes": 13,
                            "is_out": False,
                        }
                    ],
                    "bowling": [],
                }
            ],
            "super_overs": [],
        }

        from app.ai.answer_service import answer_match_awards_question

        result = answer_match_awards_question(match_id=335982)
        mock_gen.assert_not_called()

        lines = result.splitlines()
        self.assertTrue(lines[0].startswith("🏆 Player of the Match:"))
        self.assertIn("BB McCullum", lines[0])
        self.assertLess(result.index("BB McCullum"), result.index("**IPL 2007/08 Match**"))
        self.assertIn("- Date: 18 April 2008", result)
        self.assertIn("- Result: Kolkata Knight Riders won by 140 runs", result)
        self.assertIn("- Match ID: 335982", result)
        self.assertIn("- Team: Kolkata Knight Riders", result)
        self.assertIn("- Performance: Batting: 158* (73 balls, 10x4, 13x6)", result)

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_match_scorecard")
    @patch("app.ai.answer_service.get_match_details")
    @patch("app.ai.answer_service.get_match_awards")
    def test_potm_missing_data_reports_unavailable_without_llm_guess(
        self, mock_awards, mock_details, mock_scorecard, mock_gen
    ):
        from app.ai.answer_service import answer_match_awards_question

        mock_awards.return_value = []
        mock_details.return_value = {
            "match_id": 501265,
            "season": "2011",
            "match_date": "2011-05-21",
            "venue": "Feroz Shah Kotla",
            "city": "Delhi",
            "stage": None,
            "teams": [
                {"team_name": "Delhi Capitals"},
                {"team_name": "Pune Warriors"},
            ],
            "result": {"summary": "No result (match abandoned)"},
        }
        mock_scorecard.return_value = None

        match_res = answer_match_awards_question(match_id=501265)
        self.assertIn("unavailable in the database", match_res.lower())
        self.assertIn("501265", match_res)
        self.assertNotIn("🏆 Player of the Match:", match_res)

        final_res = answer_match_awards_question(season="2026", final_only=True)
        self.assertIn("unavailable in the database", final_res.lower())
        self.assertIn("IPL 2026 Final", final_res)
        mock_gen.assert_not_called()

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_bowling_leaderboard")
    def test_answer_leaderboard_question_formats_dot_balls_and_empty_results(
        self, mock_bowling, mock_gen
    ):
        from app.ai.answer_service import answer_leaderboard_question

        mock_bowling.return_value = [
            {"player_name": "B Kumar", "dot_balls": 1897, "matches_played": 176},
            {"player_name": "SP Narine", "dot_balls": 1784, "matches_played": 177},
        ]
        result = answer_leaderboard_question(category="dot_balls", question_type="bowling", limit=10)
        mock_bowling.assert_called_once_with(category="dot_balls", season=None, limit=10)
        self.assertIn("Rank | Player | Dot Balls | Matches", result)
        self.assertIn("1 | B Kumar | 1897 | 176", result)
        self.assertIn("2 | SP Narine | 1784 | 177", result)

        mock_bowling.return_value = []
        empty_res = answer_leaderboard_question(
            category="dot_balls", question_type="bowling", season="2099", limit=5
        )
        self.assertIn("No leaderboard records found in IPL season 2099.", empty_res)
        mock_gen.assert_not_called()

    @patch("app.ai.answer_service.generate_response")
    @patch("app.ai.answer_service.get_most_dot_balls_in_match")
    def test_answer_leaderboard_question_formats_single_match_dot_balls(
        self, mock_single, mock_gen
    ):
        from app.ai.answer_service import answer_leaderboard_question

        mock_single.return_value = [
            {
                "player_name": "Suyash Sharma",
                "season": "2026",
                "match_id": 1529282,
                "dot_balls": 20,
                "legal_balls": 24,
            }
        ]
        result = answer_leaderboard_question(
            category="dot_balls",
            question_type="single_match_dot_balls",
            limit=5,
        )
        mock_single.assert_called_once_with(season=None, limit=5)
        self.assertIn("Rank | Player | Season | Match ID | Dot Balls | Overs", result)
        self.assertIn("1 | Suyash Sharma | 2026 | 1529282 | 20 | 4.0", result)
        mock_gen.assert_not_called()


if __name__ == "__main__":
    unittest.main()

