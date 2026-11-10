# CricketGPT — Scripts Directory

## Responsibility
Houses developer utilities, data verification tools, and administrative scripts.

### Categories of Scripts
1. **Inspection & Analysis:**
   - `inspect_dataset.py`: Read-only inspection of the Cricsheet JSON folder.
   - `inspect_player_registry.py`, `analyze_player_registry.py`: Player registry coverage analysis.
   - `inspect_first_match.py`, `inspect_innings_structure.py`, `inspect_penalty_deliveries.py`: Data structure edge-case verification.
2. **Data Integrity Checks:**
   - `check_match_readiness.py`: Validates match prerequisites before ingestion.
   - `check_innings_totals.py`, `check_delivery_runs.py`, `check_wickets.py`: Verifies scorecard arithmetic.
   - `check_player_identity.py`, `check_harmeet_identity.py`: Resolves ambiguous cricketer identities.
3. **Database Operations & Testing:**
   - `test_db_connection.py`: Tests Supabase connection via `psycopg`.
   - `import_players.py`, `preview_player_import.py`: Populates the `players` table from Cricsheet registries.
   - `import_one_match.py`: Imports a single match file (e.g. `335982`) for end-to-end verification.
   - `validate_team_mapping.py`, `test_resolver.py`: Verifies franchise alias resolution.

