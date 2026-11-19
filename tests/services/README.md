# CricketGPT — Service Layer Tests

## Responsibility
Tests domain business logic and SQL query construction.

### Test Focus Areas
- Verification of cricket metric formulas (batting average with not-outs, strike rate, economy rate).
- Verification that bowler runs do NOT include byes, leg-byes, or penalty runs.
- Verification that non-bowler dismissals (run out, retired hurt) do NOT increment bowler wickets.
- Correct handling of Super Overs and abandoned matches.

