# CricketGPT — Services Layer

## Responsibility
Encapsulates all domain logic and analytical SQL querying.

### Design Principles
- Routes in `app/api/` delegate all calculation and database queries to this layer.
- All numerical IPL cricket statistics must be calculated directly via PostgreSQL queries using parameterized SQL.
- Never let LLMs approximate or fabricate numerical statistics when database queries can compute verified facts.

### Sub-packages
- `statistics/`: Advanced cricket metric calculations (averages, strike rates, economy, leaderboards).
- `matches/`: Scorecard retrieval, ball-by-ball queries, match filtering.
- `players/`: Career statistics, player comparisons, form tracking.
- `teams/`: Franchise records, head-to-head records, season-by-season standings.

