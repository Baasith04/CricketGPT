"""
Tests for LangChain orchestrator: retry, fallback, and provider chain construction.

All tests use unittest.mock — no real API calls, no database access.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_cfg(
    enabled=True,
    max_retries=2,
    retry_min_seconds=0.0,
    retry_max_seconds=0.0,
    tool_timeout_seconds=5,
    fallback_enabled=True,
    provider_order=None,
):
    from app.ai.llm.langchain_config import LangChainConfig
    return LangChainConfig(
        enabled=enabled,
        max_tool_iterations=3,
        max_retries=max_retries,
        retry_min_seconds=retry_min_seconds,
        retry_max_seconds=retry_max_seconds,
        tool_timeout_seconds=tool_timeout_seconds,
        fallback_enabled=fallback_enabled,
        provider_order=provider_order or ["groq", "gemini", "mistral"],
    )


def _mock_llm(response_text: str) -> MagicMock:
    llm = MagicMock()
    msg = MagicMock()
    msg.content = response_text
    llm.invoke.return_value = msg
    return llm


def _failing_llm(exc: Exception, fail_times: int = 99) -> MagicMock:
    llm = MagicMock()
    llm.invoke.side_effect = [exc] * fail_times
    return llm


# ---------------------------------------------------------------------------
# LangChainConfig tests
# ---------------------------------------------------------------------------

class TestLangChainConfig:
    def test_defaults_disabled(self):
        """LANGCHAIN_ENABLED must default to false (safe)."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove any override
            os.environ.pop("LANGCHAIN_ENABLED", None)
            from app.ai.llm.langchain_config import LangChainConfig
            cfg = LangChainConfig.from_env()
            assert cfg.enabled is False

    def test_enabled_via_env(self):
        with patch.dict(os.environ, {"LANGCHAIN_ENABLED": "true"}):
            from app.ai.llm.langchain_config import LangChainConfig
            cfg = LangChainConfig.from_env()
            assert cfg.enabled is True

    def test_int_params(self):
        env = {
            "LANGCHAIN_ENABLED": "true",
            "LANGCHAIN_MAX_RETRIES": "3",
            "LANGCHAIN_MAX_TOOL_ITERATIONS": "7",
            "LANGCHAIN_TOOL_TIMEOUT_SECONDS": "20",
        }
        with patch.dict(os.environ, env):
            from app.ai.llm.langchain_config import LangChainConfig
            cfg = LangChainConfig.from_env()
            assert cfg.max_retries == 3
            assert cfg.max_tool_iterations == 7
            assert cfg.tool_timeout_seconds == 20

    def test_provider_order_parsed(self):
        with patch.dict(os.environ, {"AI_PROVIDER_ORDER": "gemini,groq"}):
            from app.ai.llm.langchain_config import LangChainConfig
            cfg = LangChainConfig.from_env()
            assert cfg.provider_order == ["gemini", "groq"]

    def test_invalid_int_uses_default(self):
        with patch.dict(os.environ, {"LANGCHAIN_MAX_RETRIES": "not_a_number"}):
            from app.ai.llm.langchain_config import LangChainConfig
            cfg = LangChainConfig.from_env()
            assert cfg.max_retries == 2  # default


# ---------------------------------------------------------------------------
# generate_with_langchain — disabled path
# ---------------------------------------------------------------------------

class TestGenerateDisabled:
    def test_returns_none_when_disabled(self):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        cfg = _make_cfg(enabled=False)
        result = generate_with_langchain("Who won IPL 2024?", cfg)
        assert result is None

    def test_returns_none_for_empty_prompt(self):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        cfg = _make_cfg(enabled=True)
        result = generate_with_langchain("", cfg)
        assert result is None


# ---------------------------------------------------------------------------
# _invoke_with_retry tests
# ---------------------------------------------------------------------------

class TestRetry:
    def test_success_on_first_attempt(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = _mock_llm("Great answer!")
        result = _invoke_with_retry(llm, ["msg"], "groq", max_retries=2, min_wait=0, max_wait=0)
        assert result == "Great answer!"
        assert llm.invoke.call_count == 1

    def test_retries_on_timeout(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = MagicMock()
        msg = MagicMock()
        msg.content = "Recovered!"
        llm.invoke.side_effect = [TimeoutError("timed out"), msg]
        result = _invoke_with_retry(llm, ["msg"], "groq", max_retries=2, min_wait=0, max_wait=0)
        assert result == "Recovered!"
        assert llm.invoke.call_count == 2

    def test_retries_on_rate_limit(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = MagicMock()
        msg = MagicMock()
        msg.content = "Done!"
        llm.invoke.side_effect = [RuntimeError("429 rate limit"), msg]
        result = _invoke_with_retry(llm, ["msg"], "groq", max_retries=2, min_wait=0, max_wait=0)
        assert result == "Done!"

    def test_raises_after_max_retries(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = _failing_llm(TimeoutError("timeout"), fail_times=10)
        with pytest.raises(RuntimeError, match="failed after"):
            _invoke_with_retry(llm, ["msg"], "groq", max_retries=2, min_wait=0, max_wait=0)
        assert llm.invoke.call_count == 3  # initial + 2 retries

    def test_non_retriable_401_raises_immediately(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = _failing_llm(RuntimeError("401 unauthorized"), fail_times=5)
        with pytest.raises(RuntimeError):
            _invoke_with_retry(llm, ["msg"], "groq", max_retries=3, min_wait=0, max_wait=0)
        assert llm.invoke.call_count == 1  # no retries

    def test_non_retriable_403_raises_immediately(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = _failing_llm(RuntimeError("403 forbidden"), fail_times=5)
        with pytest.raises(RuntimeError):
            _invoke_with_retry(llm, ["msg"], "groq", max_retries=3, min_wait=0, max_wait=0)
        assert llm.invoke.call_count == 1

    def test_non_retriable_invalid_api_key(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = _failing_llm(RuntimeError("invalid api key"), fail_times=5)
        with pytest.raises(RuntimeError):
            _invoke_with_retry(llm, ["msg"], "groq", max_retries=3, min_wait=0, max_wait=0)
        assert llm.invoke.call_count == 1

    def test_non_retriable_404_not_found(self):
        from app.ai.llm.langchain_orchestrator import _invoke_with_retry
        llm = _failing_llm(RuntimeError("404 model not found"), fail_times=5)
        with pytest.raises(RuntimeError):
            _invoke_with_retry(llm, ["msg"], "groq", max_retries=3, min_wait=0, max_wait=0)
        assert llm.invoke.call_count == 1

    def test_retry_after_extraction(self):
        from app.ai.llm.langchain_orchestrator import _extract_retry_after
        # 1. From attribute
        exc_attr = Exception("Rate limited")
        exc_attr.retry_after = 2.5
        assert _extract_retry_after(exc_attr) == 2.5

        # 2. From response header
        exc_hdr = Exception("Rate limited")
        exc_hdr.response = SimpleNamespace(headers={"retry-after": "4"})
        assert _extract_retry_after(exc_hdr) == 4.0

        # 3. None when missing
        assert _extract_retry_after(Exception("other")) is None


# ---------------------------------------------------------------------------
# generate_with_langchain — fallback tests
# ---------------------------------------------------------------------------

class TestFallback:
    def _patch_build(self, chain):
        """Patch build_provider_chain to return a fixed chain."""
        return patch(
            "app.ai.llm.langchain_orchestrator.build_provider_chain",
            return_value=chain,
        )

    def _hm_patch(self):
        return patch(
            "app.ai.llm.langchain_orchestrator.HumanMessage",
            new=lambda content: content,
        )

    @patch("app.ai.llm.langchain_orchestrator.build_provider_chain")
    def test_primary_succeeds_no_fallback_needed(self, mock_build):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        from langchain_core.messages import HumanMessage
        llm = _mock_llm("Answer from groq!")
        mock_build.return_value = [("groq", llm)]
        cfg = _make_cfg(enabled=True, fallback_enabled=True, provider_order=["groq"])
        result = generate_with_langchain("Question?", cfg)
        assert result == "Answer from groq!"

    @patch("app.ai.llm.langchain_orchestrator.build_provider_chain")
    def test_fallback_to_gemini_when_groq_fails(self, mock_build):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        groq_llm = _failing_llm(TimeoutError("groq down"), fail_times=10)
        gemini_llm = _mock_llm("Answer from gemini!")
        mock_build.return_value = [("groq", groq_llm), ("gemini", gemini_llm)]
        cfg = _make_cfg(enabled=True, fallback_enabled=True, max_retries=0)
        result = generate_with_langchain("Question?", cfg)
        assert result == "Answer from gemini!"

    @patch("app.ai.llm.langchain_orchestrator.build_provider_chain")
    def test_all_providers_fail_returns_none(self, mock_build):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        groq_llm = _failing_llm(TimeoutError("groq down"), fail_times=10)
        gemini_llm = _failing_llm(TimeoutError("gemini down"), fail_times=10)
        mock_build.return_value = [("groq", groq_llm), ("gemini", gemini_llm)]
        cfg = _make_cfg(enabled=True, fallback_enabled=True, max_retries=0)
        result = generate_with_langchain("Question?", cfg)
        assert result is None

    @patch("app.ai.llm.langchain_orchestrator.build_provider_chain")
    def test_fallback_disabled_uses_only_primary(self, mock_build):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        groq_llm = _failing_llm(TimeoutError("groq down"), fail_times=10)
        gemini_llm = _mock_llm("Answer from gemini!")
        mock_build.return_value = [("groq", groq_llm), ("gemini", gemini_llm)]
        cfg = _make_cfg(enabled=True, fallback_enabled=False, max_retries=0)
        result = generate_with_langchain("Question?", cfg)
        assert result is None  # no fallback, gemini not tried

    @patch("app.ai.llm.langchain_orchestrator.build_provider_chain")
    def test_no_providers_returns_none(self, mock_build):
        from app.ai.llm.langchain_orchestrator import generate_with_langchain
        mock_build.return_value = []
        cfg = _make_cfg(enabled=True, provider_order=[])
        result = generate_with_langchain("Question?", cfg)
        assert result is None


# ---------------------------------------------------------------------------
# build_provider_chain — credential filtering
# ---------------------------------------------------------------------------

class TestBuildProviderChain:
    def test_excludes_missing_credentials(self):
        """Providers without valid API keys must be excluded."""
        from app.ai.llm.langchain_orchestrator import build_provider_chain
        env = {
            "GROQ_API_KEY": "",  # missing
            "GROQ_MODEL": "test-model",
            "GEMINI_API_KEY": "",  # missing
            "GEMINI_MODEL": "gemini-2.5-flash",
        }
        with patch.dict(os.environ, env):
            chain = build_provider_chain(["groq", "gemini"], tool_timeout=10)
            assert chain == []

    def test_excludes_placeholder_credentials(self):
        from app.ai.llm.langchain_orchestrator import build_provider_chain
        env = {
            "GROQ_API_KEY": "your_groq_api_key",
            "GROQ_MODEL": "openai/gpt-4o",
        }
        with patch.dict(os.environ, env):
            chain = build_provider_chain(["groq"], tool_timeout=10)
            assert chain == []


# ---------------------------------------------------------------------------
# Tool calling & Agent fallback tests
# ---------------------------------------------------------------------------

class TestToolCallingAndAgentFallback:
    def test_build_tool_calling_chain_filters_unsupported(self):
        from app.ai.llm.langchain_orchestrator import build_tool_calling_chain
        mock_groq = MagicMock()
        mock_groq.bind_tools.return_value = "groq_tools"
        mock_other = MagicMock()

        with patch("app.ai.llm.langchain_orchestrator.build_provider_chain") as mock_chain:
            mock_chain.return_value = [("groq", mock_groq), ("unsupported_p", mock_other)]
            cfg = _make_cfg(enabled=True)
            res = build_tool_calling_chain(["dummy_tool"], cfg)
            assert len(res) == 1
            assert res[0] == ("groq", "groq_tools")

    def test_agent_returns_answer_on_direct_response(self):
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True)

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.tool_calls = []
        mock_resp.content = "Final direct answer"
        mock_llm.invoke.return_value = mock_resp

        with patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain:
            mock_chain.return_value = [("groq", mock_llm)]
            res = run_with_tools("Hello?", cfg)
            assert res is not None
            assert res["answer"] == "Final direct answer"
            assert res["provider"] == "groq"
            assert res["iterations"] == 1

    def test_agent_executes_tool_call_and_answers(self):
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True)

        mock_llm = MagicMock()
        tool_call_resp = MagicMock()
        tool_call_resp.tool_calls = [{
            "name": "get_match_result_tool",
            "args": {"match_id": 1426312},
            "id": "call_1",
        }]
        final_resp = MagicMock()
        final_resp.tool_calls = []
        final_resp.content = "KKR won the final by 8 wickets."

        mock_llm.invoke.side_effect = [tool_call_resp, final_resp]

        with (
            patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain,
            patch("app.services.matches.match_service.get_match_result") as mock_match,
        ):
            mock_chain.return_value = [("groq", mock_llm)]
            mock_match.return_value = {
                "season": "2024",
                "match_date": "2024-05-26",
                "team1": "SRH",
                "team2": "KKR",
                "venue": "Chennai",
                "winner": "KKR",
                "result_type": "wickets",
                "win_by_wickets": 8,
                "win_by_runs": None,
            }
            res = run_with_tools("Who won the 2024 final?", cfg)
            assert res is not None
            assert "KKR" in res["answer"]
            assert res["iterations"] == 2
            assert "get_match_result_tool" in res["tools_called"]

    def test_agent_parses_json_string_tool_args(self):
        from app.ai.langchain_agent import _execute_tool
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "Tool result"

        res = _execute_tool(mock_tool, '{"match_id": 1426312}')
        assert res == "Tool result"
        mock_tool.invoke.assert_called_once_with({"match_id": 1426312})

    def test_agent_falls_back_to_gemini_when_groq_fails(self):
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True, fallback_enabled=True, max_retries=0)

        failing_groq = MagicMock()
        failing_groq.invoke.side_effect = RuntimeError("Groq down")

        success_gemini = MagicMock()
        gemini_resp = MagicMock()
        gemini_resp.tool_calls = []
        gemini_resp.content = "Gemini answer"
        success_gemini.invoke.return_value = gemini_resp

        with patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain:
            mock_chain.return_value = [("groq", failing_groq), ("gemini", success_gemini)]
            res = run_with_tools("Hello?", cfg)
            assert res is not None
            assert res["provider"] == "gemini"
            assert res["answer"] == "Gemini answer"

    def test_agent_all_providers_fail_returns_none(self):
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True, fallback_enabled=True, max_retries=0)

        failing_groq = MagicMock()
        failing_groq.invoke.side_effect = RuntimeError("Groq down")
        failing_gemini = MagicMock()
        failing_gemini.invoke.side_effect = RuntimeError("Gemini down")

        with patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain:
            mock_chain.return_value = [("groq", failing_groq), ("gemini", failing_gemini)]
            res = run_with_tools("Hello?", cfg)
            assert res is None

    def test_multi_step_tool_calling_executes_both_tools(self):
        """A multi-step question executes tool 1, then tool 2, then produces final answer."""
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True, max_retries=0)

        mock_llm = MagicMock()
        # Turn 1: tool 1
        resp_turn1 = MagicMock()
        resp_turn1.tool_calls = [{"name": "get_player_statistics", "args": {"player_name": "Kohli"}, "id": "call_1"}]
        # Turn 2: tool 2
        resp_turn2 = MagicMock()
        resp_turn2.tool_calls = [{"name": "compare_ipl_players", "args": {"player_one": "Kohli", "player_two": "Rohit"}, "id": "call_2"}]
        # Turn 3: final answer
        resp_turn3 = MagicMock()
        resp_turn3.tool_calls = []
        resp_turn3.content = "Multi-step analysis: Kohli leads in runs, Rohit in strike rate."

        mock_llm.invoke.side_effect = [resp_turn1, resp_turn2, resp_turn3]

        with (
            patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain,
            patch("app.services.players.player_service.get_player_batting_stats", return_value="Kohli 8004 runs"),
            patch("app.services.players.bowling_service.get_player_bowling_stats", return_value="Kohli 4 wickets"),
            patch("app.services.players.player_comparison_service.compare_players", return_value="Comparison details"),
        ):
            mock_chain.return_value = [("groq", mock_llm)]
            res = run_with_tools("Compare Kohli and Rohit with statistics", cfg)

            assert res is not None
            assert res["iterations"] == 3
            assert res["tools_called"] == ["get_player_statistics", "compare_ipl_players"]
            assert "Multi-step analysis" in res["answer"]
            assert mock_llm.invoke.call_count == 3

    def test_groq_fails_after_first_tool_call_gemini_restarts_cleanly(self):
        """If primary fails on turn 2 after executing tool 1, fallback starts clean without mixing state."""
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True, fallback_enabled=True, max_retries=0)

        # Groq succeeds on turn 1 with tool call, then fails on turn 2
        groq_turn1 = MagicMock()
        groq_turn1.tool_calls = [{"name": "get_match_result_tool", "args": {"match_id": 1426312}, "id": "groq_call_1"}]

        mock_groq = MagicMock()
        mock_groq.invoke.side_effect = [groq_turn1, RuntimeError("Groq 503 Service Unavailable")]

        # Gemini starts fresh and answers
        gemini_turn1 = MagicMock()
        gemini_turn1.tool_calls = [{"name": "get_match_result_tool", "args": {"match_id": 1426312}, "id": "gemini_call_1"}]
        gemini_turn2 = MagicMock()
        gemini_turn2.tool_calls = []
        gemini_turn2.content = "KKR won the 2024 final via Gemini."

        mock_gemini = MagicMock()
        mock_gemini.invoke.side_effect = [gemini_turn1, gemini_turn2]

        with (
            patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain,
            patch("app.services.matches.match_service.get_match_result", return_value={"winner": "KKR", "season": "2024"}),
        ):
            mock_chain.return_value = [("groq", mock_groq), ("gemini", mock_gemini)]
            res = run_with_tools("Who won the 2024 final?", cfg)

            assert res is not None
            assert res["provider"] == "gemini"
            assert res["answer"] == "KKR won the 2024 final via Gemini."
            # Verify partial results from Groq were NOT mixed into Gemini's result
            assert res["tools_called"] == ["get_match_result_tool"]
            assert res["iterations"] == 2

            # Crucial check: verify Gemini's first invoke received ONLY the original HumanMessage,
            # not Groq's tool_calls or ToolMessages!
            gemini_first_call_messages = mock_gemini.invoke.call_args_list[0].args[0]
            assert len(gemini_first_call_messages) == 1
            assert gemini_first_call_messages[0].content == "Who won the 2024 final?"

    def test_agent_respects_max_tool_iteration_limit(self):
        """If model loops tools endlessly, agent stops at max_tool_iterations and returns None."""
        from app.ai.langchain_agent import run_with_tools
        cfg = _make_cfg(enabled=True, fallback_enabled=False, max_retries=0)
        # max_tool_iterations is 3 in _make_cfg

        mock_llm = MagicMock()
        looping_resp = MagicMock()
        looping_resp.tool_calls = [{"name": "get_match_result_tool", "args": {"match_id": 1}, "id": "loop_call"}]
        mock_llm.invoke.return_value = looping_resp

        with (
            patch("app.ai.llm.langchain_orchestrator.build_tool_calling_chain") as mock_chain,
            patch("app.services.matches.match_service.get_match_result", return_value={"winner": "MI"}),
        ):
            mock_chain.return_value = [("groq", mock_llm)]
            res = run_with_tools("Infinite loop question?", cfg)
            # Must hit iteration limit and return None (falling through to router)
            assert res is None
            assert mock_llm.invoke.call_count == 3

