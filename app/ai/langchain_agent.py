"""
CricketGPT LangChain Agent — Tool-calling orchestration layer.

This module sits ABOVE the existing route_question() pipeline.  When
LANGCHAIN_ENABLED=true the chat endpoint tries this agent first; if it
returns None for any reason the caller falls through to route_question()
unchanged.

Tool-calling loop
-----------------
1. Bind ALL_CRICKET_TOOLS to the first provider that supports tool calling.
2. Send the user question as a HumanMessage.
3. If the model returns tool calls, execute each tool, append ToolMessages,
   and continue the loop.
4. Stop when the model returns plain text, or after LANGCHAIN_MAX_TOOL_ITERATIONS.
5. Return the final assistant text, plus metadata for observability logging.

Safe fallback rules
-------------------
• Provider has no tool-calling support → return None (use legacy router).
• Any tool call raises → return a graceful error string as the tool result
  and continue (never crash the loop).
• Max iterations reached without a final answer → return None.
• Any unexpected exception → log sanitized, return None.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports so this module can be imported without crashing when LangChain
# is not installed or LANGCHAIN_ENABLED=false.
# ---------------------------------------------------------------------------


def _lc_imports() -> Tuple[Any, Any, Any]:
    """Return (HumanMessage, AIMessage, ToolMessage) or raise ImportError."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # type: ignore
    return HumanMessage, AIMessage, ToolMessage


# ---------------------------------------------------------------------------
# Tool execution helper
# ---------------------------------------------------------------------------

def _execute_tool(tool_obj: Any, tool_input: Any) -> str:
    """Execute a single tool safely, returning a string result."""
    import json

    args = tool_input
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    elif not isinstance(args, dict):
        args = {}

    try:
        result = tool_obj.invoke(args)
        if isinstance(result, str):
            return result
        return str(result)
    except Exception as exc:
        logger.warning(
            "Tool '%s' raised during execution: %s",
            getattr(tool_obj, "name", "unknown"),
            str(exc)[:200],
        )
        return f"[Tool error: {type(exc).__name__} — {str(exc)[:100]}]"


# ---------------------------------------------------------------------------
# Main agent entrypoint
# ---------------------------------------------------------------------------

def run_with_tools(
    question: str,
    cfg,  # LangChainConfig
) -> Optional[Dict[str, Any]]:
    """
    Run the LangChain tool-calling agent for a user question with retry and provider fallback.

    Returns
    -------
    dict | None
        On success: {"answer": str, "provider": str, "tools_called": list, "iterations": int}
        On failure / disabled: None  (caller should fall through to legacy pipeline)
    """
    if not cfg.enabled:
        return None

    if not question or not question.strip():
        return None

    start_time = time.monotonic()

    try:
        HumanMessage, AIMessage, ToolMessage = _lc_imports()
    except ImportError as exc:
        logger.warning("LangChain not available: %s", exc)
        return None

    # Import tool list and orchestrator
    try:
        from app.ai.tools.cricket_tools import ALL_CRICKET_TOOLS
        from app.ai.llm.langchain_orchestrator import (
            build_tool_calling_chain,
            _invoke_with_retry_response,
        )
    except ImportError as exc:
        logger.warning("LangChain agent imports failed: %s", exc)
        return None

    # Get all tool-capable LLMs in configured fallback order
    tool_chain = build_tool_calling_chain(ALL_CRICKET_TOOLS, cfg)
    if not tool_chain:
        logger.info("LangChain: no tool-calling provider available; falling through.")
        return None

    tool_map: Dict[str, Any] = {t.name: t for t in ALL_CRICKET_TOOLS}

    # Attempt with primary, then fall back to next provider if needed
    for provider_name, llm_with_tools in tool_chain:
        messages: List[Any] = [HumanMessage(content=question)]
        tools_called: List[str] = []
        iterations = 0
        provider_failed = False

        while iterations < cfg.max_tool_iterations:
            iterations += 1

            try:
                response = _invoke_with_retry_response(
                    llm=llm_with_tools,
                    messages=messages,
                    provider=provider_name,
                    max_retries=cfg.max_retries,
                    min_wait=cfg.retry_min_seconds,
                    max_wait=cfg.retry_max_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "LangChain agent: provider %s failed on iteration %d: %s",
                    provider_name,
                    iterations,
                    str(exc)[:120],
                )
                provider_failed = True
                break

            messages.append(response)

            # Check for tool calls in the response
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                # Model returned a plain-text answer
                content = getattr(response, "content", None) or str(response)
                if not content or not content.strip():
                    logger.warning("LangChain agent: empty final response from %s.", provider_name)
                    provider_failed = True
                    break

                elapsed = time.monotonic() - start_time
                logger.info(
                    "LangChain agent: completed in %.2fs via %s, %d iteration(s), tools=%s.",
                    elapsed,
                    provider_name,
                    iterations,
                    tools_called,
                )
                return {
                    "answer": content.strip(),
                    "provider": provider_name,
                    "tools_called": tools_called,
                    "iterations": iterations,
                    "elapsed_seconds": round(elapsed, 2),
                }

            # Execute each requested tool and add results to message history
            for tc in tool_calls:
                tool_name = tc.get("name") or tc.get("function", {}).get("name", "")
                raw_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
                tool_id = tc.get("id", f"call_{tool_name}_{iterations}")

                tools_called.append(tool_name)
                logger.info("LangChain agent: calling tool '%s' with args %s", tool_name, raw_args)

                if tool_name not in tool_map:
                    tool_result = f"[Unknown tool '{tool_name}'. Available: {', '.join(tool_map.keys())}]"
                else:
                    tool_result = _execute_tool(tool_map[tool_name], raw_args)

                messages.append(
                    ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_id,
                    )
                )

        if not provider_failed and iterations >= cfg.max_tool_iterations:
            logger.warning(
                "LangChain agent: provider %s reached max iterations (%d) without final answer.",
                provider_name,
                cfg.max_tool_iterations,
            )

        if not cfg.fallback_enabled:
            break

    logger.warning("LangChain agent: all tool-capable providers exhausted. Falling through.")
    return None

