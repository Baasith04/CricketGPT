# CricketGPT — Prompt Engineering

## Responsibility
Houses structured prompt templates ensuring responses are strictly grounded in retrieved database records and RAG context.

### Prompt Templates
- `intent_prompt.py`: Few-shot prompt for extracting intent, entities (player, team, season), and routing category.
- `answer_prompt.py`: System prompt guiding the LLM to format SQL results and RAG excerpts into clear, conversational markdown.
- `clarification_prompt.py`: Handles ambiguous queries (e.g. "Who won the final?" -> asks which year).

