"""
LangChain orchestrator: retry, fallback, and provider chain construction.

This module is intentionally self-contained and additive — it does NOT touch
any existing service, SQL query, or RAG pipeline.  When LANGCHAIN_ENABLED=false
(the default) every public function returns None and the caller falls through
to the existing generate_response() path.

Supported providers and their LangChain wrappers
-------------------------------------------------
  groq     → langchain_groq.ChatGroq
  gemini   → langchain_google_genai.ChatGoogleGenerativeAI
  mistral  → langchain_mistralai.ChatMistralAI
  nvidia   → langchain_nvidia_ai_endpoints (optional, skipped if unavailable)

Retry policy
------------
  • Retried on: TimeoutError, ConnectionError, RateLimitError (HTTP 429),
    ServiceUnavailableError (HTTP 503), generic RuntimeError
  • Never retried on: AuthenticationError (401/403), BadRequestError (400),
    ValueError (bad arguments)

Fallback policy
---------------
  Groq → Gemini → Mistral → (NVIDIA if configured)
  Providers with missing / placeholder credentials are excluded automatically.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Placeholder detection (mirrors app/ai/llm/client.py)
# ---------------------------------------------------------------------------
_PLACEHOLDER_PREFIXES = ("your_", "your-", "<your")


def _is_placeholder(value: str) -> bool:
    lower = value.lower()
    return any(lower.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _has_credentials(provider: str) -> bool:
    key = os.getenv(f"{provider.upper()}_API_KEY", "").strip()
    model = os.getenv(f"{provider.upper()}_MODEL", "").strip()
    return bool(key and model and not _is_placeholder(key) and not _is_placeholder(model))


def _sanitize(text: str) -> str:
    """Redact API keys and bearer tokens from log strings."""
    result = str(text or "")
    for env_key in ("GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "NVIDIA_API_KEY"):
        secret = os.getenv(env_key, "").strip()
        if secret and not _is_placeholder(secret):
            result = result.replace(secret, "[REDACTED]")
    result = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", result)
    result = re.sub(r"(?i)(api[_-]?key\s*[=:]\s*)\S+", r"\1[REDACTED]", result)
    return result


# ---------------------------------------------------------------------------
# Non-retriable exception categories
# ---------------------------------------------------------------------------
_NON_RETRIABLE_SUBSTRINGS = (
    "401", "403", "unauthorized", "forbidden",
    "authentication", "invalid api key",
    "bad request", "400",
    "404", "not found", "model_not_found",
)


def _is_non_retriable(exc: Exception) -> bool:
    msg = _sanitize(str(exc)).lower()
    return any(s in msg for s in _NON_RETRIABLE_SUBSTRINGS)


def _extract_retry_after(exc: Exception) -> Optional[float]:
    """Extract Retry-After duration in seconds from exception or HTTP headers if available."""
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            pass
    for attr in ("response", "raw_response"):
        resp = getattr(exc, attr, None)
        if resp is not None and hasattr(resp, "headers"):
            headers = resp.headers
            hdr = None
            if hasattr(headers, "get"):
                hdr = headers.get("retry-after") or headers.get("Retry-After")
            if hdr is not None:
                try:
                    return float(hdr)
                except (ValueError, TypeError):
                    pass
    return None


# ---------------------------------------------------------------------------
# Build a single provider LLM instance (returns None if unavailable)
# ---------------------------------------------------------------------------
def _build_llm(provider: str, timeout: int) -> Optional[Any]:
    """Construct a LangChain chat model for the given provider."""
    if not _has_credentials(provider):
        logger.debug("LangChain: skipping provider %s — credentials missing/placeholder.", provider)
        return None

    api_key = os.getenv(f"{provider.upper()}_API_KEY", "").strip()
    model = os.getenv(f"{provider.upper()}_MODEL", "").strip()

    try:
        if provider == "groq":
            from langchain_groq import ChatGroq  # type: ignore
            return ChatGroq(
                api_key=api_key,
                model=model,
                timeout=timeout,
                max_retries=0,  # We handle retries ourselves
            )

        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
            return ChatGoogleGenerativeAI(
                google_api_key=api_key,
                model=model,
                timeout=timeout,
                max_retries=0,
            )

        if provider == "mistral":
            from langchain_mistralai import ChatMistralAI  # type: ignore
            return ChatMistralAI(
                api_key=api_key,
                model=model,
                timeout=timeout,
                max_retries=0,
            )

        if provider == "nvidia":
            try:
                from langchain_nvidia_ai_endpoints import ChatNVIDIA  # type: ignore
                return ChatNVIDIA(
                    api_key=api_key,
                    model=model,
                    max_retries=0,
                )
            except ImportError:
                logger.debug("LangChain: langchain-nvidia-ai-endpoints not installed; skipping NVIDIA.")
                return None

    except Exception as exc:
        logger.warning(
            "LangChain: failed to build %s LLM: %s",
            provider,
            _sanitize(str(exc))[:120],
        )
        return None

    return None


# ---------------------------------------------------------------------------
# Retry with exponential back-off + jitter
# ---------------------------------------------------------------------------
def _invoke_with_retry_response(
    llm: Any,
    messages: List[Any],
    provider: str,
    max_retries: int,
    min_wait: float,
    max_wait: float,
) -> Any:
    """Invoke llm with bounded exponential-jitter retries and Retry-After support."""
    import random

    attempt = 0
    last_exc: Optional[Exception] = None

    while attempt <= max_retries:
        try:
            response = llm.invoke(list(messages))
            logger.info(
                "LangChain: provider=%s succeeded on attempt %d.", provider, attempt + 1
            )
            return response
        except Exception as exc:
            last_exc = exc
            if _is_non_retriable(exc):
                logger.warning(
                    "LangChain: provider=%s non-retriable error (%s): %s",
                    provider,
                    type(exc).__name__,
                    _sanitize(str(exc))[:120],
                )
                raise

            attempt += 1
            if attempt > max_retries:
                break

            wait = min(max_wait, min_wait * (2 ** (attempt - 1)))
            jitter = random.uniform(0, wait * 0.3)
            sleep_time = wait + jitter

            retry_after = _extract_retry_after(exc)
            if retry_after is not None and retry_after > 0:
                sleep_time = min(max_wait, max(sleep_time, retry_after))

            logger.warning(
                "LangChain: provider=%s attempt %d failed (%s). Retrying in %.1fs.",
                provider,
                attempt,
                type(exc).__name__,
                sleep_time,
            )
            time.sleep(sleep_time)

    raise RuntimeError(
        f"LangChain: {provider} failed after {max_retries + 1} attempt(s)."
    ) from last_exc


def _invoke_with_retry(
    llm: Any,
    messages: List[Any],
    provider: str,
    max_retries: int,
    min_wait: float,
    max_wait: float,
) -> str:
    """Call llm.invoke(messages) with bounded exponential-jitter retries, returning text."""
    response = _invoke_with_retry_response(
        llm=llm,
        messages=messages,
        provider=provider,
        max_retries=max_retries,
        min_wait=min_wait,
        max_wait=max_wait,
    )
    return getattr(response, "content", None) or str(response)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_provider_chain(
    provider_order: List[str],
    tool_timeout: int,
) -> List[Tuple[str, Any]]:
    """
    Build an ordered list of (provider_name, llm) for all available providers.
    Providers with missing credentials are silently excluded.
    """
    chain: List[Tuple[str, Any]] = []
    for provider in provider_order:
        llm = _build_llm(provider, timeout=tool_timeout)
        if llm is not None:
            chain.append((provider, llm))
    return chain


def generate_with_langchain(
    prompt: str,
    cfg,  # LangChainConfig
) -> Optional[str]:
    """
    Attempt to generate a response using the LangChain provider chain with
    retry + fallback.  Returns None if LangChain is disabled or all providers
    fail (allowing the caller to fall through to the existing pipeline).

    Parameters
    ----------
    prompt : str
        The user prompt / formatted question.
    cfg : LangChainConfig
        Runtime configuration from langchain_config.get_langchain_config().

    Returns
    -------
    str | None
        Generated text, or None if LangChain could not produce an answer.
    """
    if not cfg.enabled:
        return None

    if not prompt or not prompt.strip():
        return None

    from langchain_core.messages import HumanMessage  # type: ignore

    chain = build_provider_chain(cfg.provider_order, cfg.tool_timeout_seconds)
    if not chain:
        logger.warning("LangChain: no providers available; falling through to legacy pipeline.")
        return None

    messages = [HumanMessage(content=prompt)]
    # Keep fallback chain (all providers after the primary)
    primary_name, primary_llm = chain[0]
    fallbacks = chain[1:] if cfg.fallback_enabled else []

    # Try primary with retry
    try:
        return _invoke_with_retry(
            primary_llm,
            messages,
            primary_name,
            max_retries=cfg.max_retries,
            min_wait=cfg.retry_min_seconds,
            max_wait=cfg.retry_max_seconds,
        )
    except Exception as primary_exc:
        logger.warning(
            "LangChain: primary provider %s exhausted: %s",
            primary_name,
            _sanitize(str(primary_exc))[:120],
        )

    # Try fallbacks one by one
    for fb_name, fb_llm in fallbacks:
        try:
            logger.info("LangChain: falling back to %s.", fb_name)
            return _invoke_with_retry(
                fb_llm,
                messages,
                fb_name,
                max_retries=cfg.max_retries,
                min_wait=cfg.retry_min_seconds,
                max_wait=cfg.retry_max_seconds,
            )
        except Exception as fb_exc:
            logger.warning(
                "LangChain: fallback provider %s failed: %s",
                fb_name,
                _sanitize(str(fb_exc))[:120],
            )

    # All providers exhausted — return None so caller uses legacy pipeline
    logger.error("LangChain: all providers exhausted. Falling through to legacy pipeline.")
    return None


def build_tool_calling_chain(
    tools: List[Any],
    cfg,  # LangChainConfig
) -> List[Tuple[str, Any]]:
    """
    Build an ordered list of (provider_name, llm_bound_with_tools) for all
    configured providers that support tool calling and have valid credentials.
    """
    if not cfg.enabled:
        return []

    _TOOL_CALLING_PROVIDERS = {"groq", "gemini", "mistral"}
    chain = build_provider_chain(cfg.provider_order, cfg.tool_timeout_seconds)
    tool_chain: List[Tuple[str, Any]] = []

    for provider_name, llm in chain:
        if provider_name not in _TOOL_CALLING_PROVIDERS:
            logger.debug("LangChain: provider %s does not support tool calling; skipping.", provider_name)
            continue
        try:
            llm_with_tools = llm.bind_tools(tools)
            tool_chain.append((provider_name, llm_with_tools))
            logger.info("LangChain: bound %d tools to provider %s.", len(tools), provider_name)
        except Exception as exc:
            logger.warning(
                "LangChain: failed to bind tools to %s: %s",
                provider_name,
                _sanitize(str(exc))[:80],
            )

    return tool_chain


def get_llm_with_tools(
    tools: List[Any],
    cfg,  # LangChainConfig
) -> Optional[Tuple[str, Any]]:
    """
    Return (provider_name, llm_bound_with_tools) for the first provider that
    supports tool/function calling.  Returns None if no provider is available
    or tool calling is not possible.
    """
    tool_chain = build_tool_calling_chain(tools, cfg)
    return tool_chain[0] if tool_chain else None

