# CricketGPT — Statistics Services

## Responsibility
Executes analytical SQL queries to compute verified IPL statistics.

### Key Calculations
- **Batting Average:** $\text{Runs} / \text{Dismissals}$ (handles not-outs without division by zero).
- **Strike Rate:** $(\text{Runs} \times 100.0) / \text{Balls Faced}$ (excluding wides).
- **Bowling Economy:** $(\text{Runs Conceded} \times 6.0) / \text{Legal Balls Bowled}$ (excluding byes, leg-byes, and penalty runs).
- **Bowling Average:** $\text{Runs Conceded} / \text{Bowler Wickets}$ (where `is_bowler_credit = TRUE`).
- **Leaderboards:** Top run scorers (Orange Cap), top wicket-takers (Purple Cap), highest individual scores, best bowling figures.

