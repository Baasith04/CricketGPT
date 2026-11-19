"""
LangChain configuration loaded from environment variables.
All settings have safe defaults so LANGCHAIN_ENABLED=false preserves existing behaviour completely.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _bool_env(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes"}


def _int_env(key: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(key, str(default)).strip()))
    except ValueError:
        return default


def _float_env(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)).strip())
    except ValueError:
        return default


def _list_env(key: str, default: str) -> List[str]:
    raw = os.getenv(key, default).strip()
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class LangChainConfig:
    enabled: bool
    max_tool_iterations: int
    max_retries: int
    retry_min_seconds: float
    retry_max_seconds: float
    tool_timeout_seconds: int
    fallback_enabled: bool
    provider_order: List[str]

    @classmethod
    def from_env(cls) -> "LangChainConfig":
        return cls(
            enabled=_bool_env("LANGCHAIN_ENABLED", False),
            max_tool_iterations=_int_env("LANGCHAIN_MAX_TOOL_ITERATIONS", 5),
            max_retries=_int_env("LANGCHAIN_MAX_RETRIES", 2),
            retry_min_seconds=_float_env("LANGCHAIN_RETRY_MIN_SECONDS", 1.0),
            retry_max_seconds=_float_env("LANGCHAIN_RETRY_MAX_SECONDS", 8.0),
            tool_timeout_seconds=_int_env("LANGCHAIN_TOOL_TIMEOUT_SECONDS", 15),
            fallback_enabled=_bool_env("LANGCHAIN_FALLBACK_ENABLED", True),
            provider_order=_list_env(
                "AI_PROVIDER_ORDER", "groq,gemini,mistral,nvidia"
            ),
        )


# Module-level singleton — re-read on import so tests can patch env vars.
def get_langchain_config() -> LangChainConfig:
    return LangChainConfig.from_env()

