# CricketGPT Knowledge Base

Place genuine `.md`, `.txt`, `.json`, or `.pdf` source documents here (rules, season summaries, match reports, player profiles, team histories) for ingestion into Supabase `pgvector`.

Optional Markdown frontmatter fields:
```yaml
---
title: Document Title
doc_type: match_report | season_summary | player_profile | team_history | cricket_rule | general_knowledge
season: 2024
match_id: 1426312
teams: [Kolkata Knight Riders, Sunrisers Hyderabad]
players: [V Kohli, RG Sharma]
source_url: https://...
---
```

Run incremental ingestion via CLI:
```powershell
venv\Scripts\python scripts/ingest_rag.py --migrate --knowledge-dir knowledge_base --match-summaries --seasons 2024 2023
```

