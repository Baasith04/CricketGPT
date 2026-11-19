"""
Sanitized server-side exception logging helpers.

Logs full exception types and tracebacks for backend debugging while redacting
database DSNs, passwords, API keys, and tokens so secrets never appear in logs.
"""

import logging
import re
import traceback


_SENSITIVE_PATTERNS = (
    # Database / URL credentials: scheme://user:password@host -> scheme://***:***@host
    (re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^@\s]+@"), r"\1***:***@"),
    # Key=value or header-style secrets
    (
        re.compile(
            r"(?i)\b(api[-_]?key|password|passwd|secret|token|authorization|dsn|database_url)"
            r"(\s*[:=]\s*['\"]?)([^'\",\s;]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    # Bearer tokens
    (re.compile(r"(?i)\bbearer\s+[a-z0-9._\-~+/]+=*"), "Bearer [REDACTED]"),
    # Common API key prefixes (OpenAI/Groq/Google)
    (re.compile(r"\b(sk-|gsk_|AIza)[A-Za-z0-9_\-]{8,}"), r"\1[REDACTED]"),
)


def sanitize_sensitive_text(text: str) -> str:
    """Redact credentials, tokens, and connection strings from log/error text."""
    if not text:
        return ""
    cleaned = str(text)
    for pattern, replacement in _SENSITIVE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def log_sanitized_exception(
    log: logging.Logger,
    context_message: str,
    exc: BaseException,
) -> None:
    """Log an exception message and formatted traceback with secrets redacted."""
    safe_err = sanitize_sensitive_text(str(exc))
    tb_text = sanitize_sensitive_text(
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    )
    log.error("%s (%s: %s)\n%s", context_message, type(exc).__name__, safe_err, tb_text)

