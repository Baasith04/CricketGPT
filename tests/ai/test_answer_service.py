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


if __name__ == "__main__":
    unittest.main()

