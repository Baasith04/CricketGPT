# CricketGPT — API Route Tests

## Responsibility
Contains integration tests for all FastAPI endpoints using `starlette.testclient.TestClient`.

### Test Modules
- `test_health.py`: Verifies `/`, `/health`, `/api/info`, and `/health/database`.
- `test_matches.py`: Tests match summary, scorecard, and filtering endpoints.
- `test_players.py`: Tests player profile, search, and career stats endpoints.
- `test_teams.py`: Tests franchise info, alias lookup, and head-to-head endpoints.
- `test_statistics.py`: Tests leaderboard endpoints and parameter validation.
- `test_sync.py`: Tests manual sync trigger permissions and status endpoints.
- `test_chat.py`: Tests conversational Q&A endpoint inputs and responses.

