# CricketGPT — AI Core Tests

## Responsibility
Tests AI routing accuracy and response grounding without incurring live Gemini API token costs.

### Test Focus Areas
- Query classification: Ensures statistical queries route to SQL and narrative queries route to RAG.
- Prompt formatting: Ensures retrieved database numbers are properly injected into LLM context.
- Fallback behavior: Ensures the system returns a safe "data unavailable" message when context is missing.
- Note: Live API calls must be mocked in automated CI/CD test runs.

