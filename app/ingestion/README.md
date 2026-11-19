# CricketGPT — Cricsheet Ingestion Engine

## Responsibility
Ingests structured IPL match files from Cricsheet into Supabase PostgreSQL with strict validation and transactional integrity.

### Existing Modules
- `parser.py`: Reads and parses Cricsheet JSON format (meta, info, innings, overs, deliveries).
- `resolver.py`: Maps franchise names and aliases to canonical `team_id`s, and player names/hashes to canonical `player_id`s.
- `importer.py`: Coordinates transactional database ingestion (matches, match_teams, match_players, innings, deliveries, delivery_wickets).

### Sub-packages
- `sync/`: Periodic synchronization, change detection, and Cricsheet HTTP client.
- `validators/`: 6-way mathematical balance checks and structural integrity rules.

