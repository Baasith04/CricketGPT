# CricketGPT — Schemas

## Responsibility
Defines type-safe Pydantic models for request validation and response serialization.

### Planned Schema Files
- `match.py`: Match summary, detailed scorecard, innings, and delivery response models.
- `player.py`: Player registry, batting profile, bowling profile, and career aggregates.
- `team.py`: Franchise summary, alias mapping, and season performance models.
- `statistics.py`: Leaderboard rankings, partnership stats, and comparative figures.
- `sync.py`: Sync trigger requests, sync history items, and status indicators.
- `chat.py`: Chat query requests, grounding metadata, source citations, and response payloads.

### Rules
- Always use explicit type hints and docstrings.
- Separate request models (e.g., `ChatRequest`) from response models (e.g., `ChatResponse`).
- Use Pydantic's `ConfigDict` where applicable.

