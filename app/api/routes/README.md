# CricketGPT — API Routes

## Responsibility
Contains resource-specific route handlers registered with the primary FastAPI application.

### Target Route Modules
- `health.py`: Application liveness, database health, and system metadata.
- `matches.py`: Match scorecards, innings breakdown, ball-by-ball queries, and season listings.
- `players.py`: Player career stats, batting/bowling figures, form, and head-to-head records.
- `teams.py`: Franchise performance, historical aliases, and head-to-head match summaries.
- `statistics.py`: Leaderboards (Orange Cap, Purple Cap, highest scores, best bowling figures).
- `sync.py`: Manual sync trigger (`POST /api/sync/run`) and sync status inspection (`GET /api/sync/status`).
- `chat.py`: Conversational Q&A endpoint powered by query routing, SQL analytics, and Gemini RAG.

