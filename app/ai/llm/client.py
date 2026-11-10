
import logging
import os

from dotenv import load_dotenv
from google import genai
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

    with genai.Client(api_key=api_key) as client:
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
        timeout=int(os.getenv("AI_TIMEOUT", "30")),
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
                str(exc)[:120],
            )
            failures.append(provider)

    raise RuntimeError(
        "All configured AI providers failed: "
        + ", ".join(failures)
    )
