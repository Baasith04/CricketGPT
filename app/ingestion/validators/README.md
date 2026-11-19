# CricketGPT — Ingestion Validators

## Responsibility
Enforces strict mathematical and relational cricket scoring rules before records are committed to the database.

### 6-Way Balance Sheet Checks
1. **Total Runs Balance:** $\sum \text{deliveries.total\_runs} = \text{innings.total\_runs}$
2. **Wicket Balance:** $\sum \text{delivery\_wickets} (\text{excl. retired hurt}) = \text{innings.total\_wickets}$
3. **Legal Ball Count:** $\sum (\text{is\_legal\_ball} = \text{TRUE}) = \text{innings.legal\_balls\_bowled}$
4. **Extras Conservation:** $\sum \text{extra\_runs} = \sum (\text{wide} + \text{noball} + \text{legbye} + \text{bye} + \text{penalty})$
5. **Batting Runs Conservation:** $\sum \text{batter\_runs} = \text{innings.total\_runs} - \sum \text{extra\_runs}$
6. **Bowling Runs Balance:** Total runs equals sum of all bowler runs plus fielding extras (byes, leg-byes, uncredited penalties).

