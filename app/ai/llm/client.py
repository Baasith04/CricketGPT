
import logging
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

PROVIDER_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
}

# Model strings that indicate a placeholder value from .env.example.
_PLACEHOLDER_PREFIXES = (
    "your_",
    "your-",
    "<your",
)


def _is_placeholder(value: str) -> bool:
    """Return True if the string looks like an unfilled .env placeholder."""
    lower = value.lower()
    return any(lower.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _get_ai_timeout_seconds() -> int:
    """Parse AI_TIMEOUT in seconds, falling back safely to 30s."""
    raw = os.getenv("AI_TIMEOUT", "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning("Invalid AI_TIMEOUT '%s'; defaulting to 30s.", raw)
        return 30


def _sanitize_provider_error(message: str) -> str:
    """Mask configured API keys and auth tokens from provider exception text."""
    sanitized = str(message or "")
    for env_key in ("GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "NVIDIA_API_KEY"):
        secret = os.getenv(env_key, "").strip()
        if secret and not _is_placeholder(secret):
            sanitized = sanitized.replace(secret, "[REDACTED]")
    sanitized = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", sanitized)
    sanitized = re.sub(r"(?i)(api[_-]?key\s*[=:]\s*)\S+", r"\1[REDACTED]", sanitized)
    return sanitized


def _generate_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")

    if not api_key or not model:
        raise RuntimeError("Gemini configuration is incomplete.")

    if _is_placeholder(api_key) or _is_placeholder(model):
        raise RuntimeError(
            "Gemini API key or model is a placeholder value. "
            "Update GEMINI_API_KEY and GEMINI_MODEL in your .env file."
        )

    timeout_ms = max(1000, _get_ai_timeout_seconds() * 1000)
    with genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_ms),
    ) as client:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return response.text


def _generate_openai_compatible(provider: str, prompt: str) -> str:
    api_key = os.getenv(f"{provider.upper()}_API_KEY")
    model = os.getenv(f"{provider.upper()}_MODEL")

    if not api_key or not model:
        raise RuntimeError(
            f"{provider} configuration is incomplete."
        )

    if _is_placeholder(api_key) or _is_placeholder(model):
        raise RuntimeError(
            f"{provider} API key or model is a placeholder value. "
            f"Update {provider.upper()}_API_KEY and "
            f"{provider.upper()}_MODEL in your .env file."
        )

    client = OpenAI(
        api_key=api_key,
        base_url=PROVIDER_URLS[provider],
        timeout=_get_ai_timeout_seconds(),
        max_retries=1,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=int(os.getenv("AI_MAX_TOKENS", "1000")),
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(f"{provider} returned an empty response.")

    return content


def _generate_with_provider(provider: str, prompt: str) -> str:
    if provider == "gemini":
        return _generate_gemini(prompt)

    if provider in PROVIDER_URLS:
        return _generate_openai_compatible(provider, prompt)

    raise ValueError(f"Unsupported provider: {provider}")


def generate_response(prompt: str) -> str:
    """Generate a response using the primary provider and configured fallbacks."""

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    primary = os.getenv(
        "AI_PRIMARY_PROVIDER", "gemini"
    ).strip().lower()

    configured_order = os.getenv(
        "AI_PROVIDER_ORDER", "gemini,groq,mistral,nvidia"
    )

    fallback_order = [
        item.strip().lower()
        for item in configured_order.split(",")
        if item.strip()
    ]

    # Always attempt the primary provider first.
    providers = list(dict.fromkeys([primary] + fallback_order))

    failures = []

    for provider in providers:
        try:
            logger.info("Trying AI provider: %s", provider)
            result = _generate_with_provider(provider, prompt)
            logger.info("AI provider succeeded: %s", provider)
            return result

        except Exception as exc:
            # Avoid logging API keys or full request details.
            logger.warning(
                "AI provider failed: %s (%s: %s)",
                provider,
                type(exc).__name__,
                _sanitize_provider_error(str(exc))[:120],
            )
            failures.append(provider)

    raise RuntimeError(
        "All configured AI providers failed: "
        + ", ".join(failures)
    )
