# CricketGPT — AI Core

## Responsibility
Coordinates language model interactions, intent routing, and final response synthesis.

### Architectural Rules
- Gemini is responsible for understanding natural-language user intent and phrasing grounded answers.
- Gemini is **never** permitted to calculate historical IPL statistics independently when database records are available.
- Always cite retrieved database facts and document sources.

### Sub-packages
- `llm/`: Google Gemini API client wrapper, error handling, rate limiting.
- `prompts/`: System instructions, structured prompts, and few-shot examples.
- `query_router/`: Intent classification to select SQL, RAG, or hybrid retrieval path.

