# CricketGPT — LLM Client

## Responsibility
Manages API connectivity with the Google Gemini API.

### Target Implementations
- Gemini API client initialization using environment variables (`GEMINI_API_KEY`).
- Token budgeting, temperature settings, and safety filters.
- Exception handling for API rate limits (HTTP 429) and network timeouts.
- Clean response text extraction and structured JSON output parsing.

