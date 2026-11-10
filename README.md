# CricketGPT Backend

AI-powered IPL cricket statistics and natural-language question-answering backend built with FastAPI, Python 3.11, Supabase PostgreSQL, Cricsheet ball-by-ball data, and multi-provider LLM fallback.

---

## Overview

CricketGPT maintains a relational + JSONB IPL match and ball-by-ball database synchronized from official [Cricsheet](https://cricsheet.org/) IPL JSON archives.

Unlike generic LLM chatbots that hallucinate cricket figures from stale training data, CricketGPT computes **all numerical statistics deterministically via parameterized PostgreSQL queries** and uses configured LLM providers only for natural-language formatting of match narratives where appropriate.

---

## Architecture

```text
app/
├── main.py                      # FastAPI application and health endpoints
├── api/routes/                  # Modular REST routers (chat, leaderboards, matches, players, teams)
├── schemas/                     # Pydantic response & request validation schemas
├── ai/
│   ├── query_router/router.py   # Entity extraction & priority-ordered intent router
│   ├── answer_service.py        # SQL-to-markdown answer formatters & LLM prompts
│   ├── llm/client.py            # Multi-provider LLM client (Gemini -> Groq -> Mistral -> NVIDIA)
│   └── prompts/system_prompt.py # Grounded system prompt enforcing SQL-only stats
├── services/
│   ├── matches/                 # Match details, scorecards, fall-of-wickets, match list
│   ├── players/                 # Player batting/bowling stats, aliases, player comparison
│   ├── teams/                   # Team records, championships, head-to-head, season matchups
│   └── statistics/              # Career/season leaderboards, awards, chases, phase stats
├── ingestion/
│   ├── parser.py                # Cricsheet JSON match parser
│   ├── resolver.py              # Team & player registry resolution
│   ├── importer.py              # Single-transaction match importer & replacement
│   ├── validators/              # Over math & scorecard reconciliation checks
│   └── sync/                    # Cricsheet ZIP download, diff planner, sync_runner
├── database/
│   ├── connection.py            # psycopg 3 connection helper with SSL enforcement
│   └── migrations/001_initial_schema.sql
└── rag/                         # Hybrid RAG: chunking, Gemini embeddings, pgvector retrieval & LLM grounding
    ├── chunking/chunker.py      # Text cleaning, recursive chunking, metadata extraction
    ├── embeddings/embedder.py   # Google Gen AI SDK (gemini-embedding-2, 768-d) + LRU cache + retries
    ├── retrieval/hybrid_retriever.py # Hybrid pgvector cosine + tsvector keyword search
    └── pipeline/rag_pipeline.py # Incremental ingestion + SQL/RAG context grounding with citations
```

---

## Key Features

- **Natural-Language Q&A (`POST /api/chat`)**:
  - **Batting & Bowling Leaderboards**: Most runs, centuries, fifties, highest batting average, best strike rate, highest individual scores, most sixes & fours, most wickets, best economy, best bowling figures, most five-wicket hauls (all-time or per-season).
  - **Player Analytics**: Career stats, season-filtered stats, season-by-season breakdowns, and side-by-side player comparisons with Cricsheet abbreviation & full-name alias support.
  - **Team Analytics**: Career and season-filtered win/loss/tie records, batting run rates, bowling economy, championship titles, and run totals.
  - **Head-to-Head & Season Matchups**: All-time head-to-head records vs. season-specific team-vs-team match lists (regardless of team order).
  - **Match Lookup**: Lookup by match ID, season final, or calendar date (`YYYY-MM-DD`, `April 14, 2024`), full scorecards (with Super Overs separated), fall of wickets, Player of the Match awards, and final-over ball-by-ball details.
  - **Advanced Records**: Highest successful run chases, biggest wins by runs/wickets, highest and lowest completed team totals, most sixes in an innings, phase statistics (Powerplay, Middle, Death overs), and extras/dismissal breakdowns.
- **Multi-Provider LLM Fallback**: Automatically falls through `gemini -> groq -> mistral -> nvidia` on rate limits, timeouts, or outages, while skipping unconfigured placeholder models cleanly.
- **Automated Cricsheet Synchronization**: Content-hashed (`SHA-256`) and revision-checked incremental sync (`sync_files` + append-only `sync_history` audit log) designed for 6-hourly cron execution on Render.

---

## Technology Stack

- **Language**: Python 3.11
- **Web Framework**: FastAPI + Uvicorn + Pydantic v2
- **Database**: Supabase PostgreSQL 15+ (`psycopg[binary]` 3.x)
- **AI SDKs**: `google-genai`, `openai` (for OpenAI-compatible Groq, Mistral, NVIDIA endpoints)
- **Testing**: `pytest`, `pytest-asyncio`, `httpx`, Starlette `TestClient`

---

## Database Setup

1. Create a Supabase project and obtain your PostgreSQL connection string (`DATABASE_URL`).
2. Apply the core schema migration (`001_initial_schema.sql`) and Hybrid RAG `pgvector` migration (`002_rag_pgvector_schema.sql`):
   ```sql
   -- 1. app/database/migrations/001_initial_schema.sql
   -- 2. app/database/migrations/002_rag_pgvector_schema.sql
   ```
   You can also apply the non-destructive RAG migration and ingest knowledge base documents + DB match summaries via CLI:
   ```powershell
   venv\Scripts\python scripts/ingest_rag.py --migrate --knowledge-dir knowledge_base --match-summaries --seasons 2024 --limit 100
   ```

---

## Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials (never commit `.env`):

```powershell
Copy-Item .env.example .env
```

Required variables:
- `DATABASE_URL`: Supabase PostgreSQL connection URI (`sslmode=require` is enforced).
- `APP_ENV`: `development` or `production`.
- `AI_PRIMARY_PROVIDER` / `AI_PROVIDER_ORDER`: e.g. `gemini` and `gemini,groq,mistral,nvidia`.
- `GEMINI_API_KEY`, `GEMINI_MODEL`, and optional fallback provider keys/models (`GROQ_*`, `MISTRAL_*`, `NVIDIA_*`).

---

## Installation & Running Locally

```powershell
# 1. Create and activate Python 3.11 virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# 2. Install dependencies
venv\Scripts\python -m pip install -r requirements.txt

# 3. Start the FastAPI server
venv\Scripts\python -m uvicorn app.main:app --reload
```

Interactive OpenAPI / Swagger UI is served at: `http://127.0.0.1:8000/docs`

---

## API Endpoints

### General & Health
- `GET /` — Welcome metadata
- `GET /health` — Service liveness check (independent of DB)
- `GET /api/info` — Application metadata
- `GET /health/database` — Live Supabase PostgreSQL connectivity check

### Natural Language Chat
- `POST /api/chat` — Body: `{"question": "..."}` -> Returns `{"question": "...", "answer": "..."}`

### Players & Leaderboards
- `GET /api/players/leaderboard/batting?limit=20`
- `GET /api/players/leaderboard/bowling?limit=20`
- `GET /api/players/{player_id}/batting`
- `GET /api/players/{player_id}/bowling`
- `GET /api/leaderboards/batting?category=runs&season=2024&limit=10&min_balls=0`
- `GET /api/leaderboards/bowling?category=wickets&season=2024&limit=10&min_balls=0`
- `GET /api/leaderboards/best-bowling?season=2024&limit=10`

### Teams
- `GET /api/teams?active_only=false`
- `GET /api/teams/championships`
- `GET /api/teams/head-to-head?team_one=CSK&team_two=MI`
- `GET /api/teams/{team_identifier}` (also `/api/teams/{team_identifier}/statistics`)

### Matches
- `GET /api/matches/{match_id}`
- `GET /api/matches/{match_id}/scorecard`
- `GET /api/matches/{match_id}/wickets`

### Hybrid RAG & Knowledge Ingestion
- `POST /api/rag/ingest` *(requires `X-API-Key` or `Authorization: Bearer <INGESTION_API_KEY>`)*
- `POST /api/rag/ingest/directory` *(protected batch ingestion)*
- `POST /api/rag/ingest/match-summaries` *(protected DB match/season summary generation)*
- `GET /api/rag/search?q=...&top_k=5&similarity_threshold=0.2&doc_type=...&season=...`

---

## Cricsheet Ingestion & Synchronization

Dry-run check (no database writes):

```powershell
venv\Scripts\python scripts/run_sync.py --dry-run --triggered-by manual
```

Full synchronization run (downloads Cricsheet IPL ZIP, compares against `sync_files`, transactionally imports new or corrected matches, logs to `sync_history`):

```powershell
venv\Scripts\python scripts/run_sync.py --triggered-by manual
```

Render deployment blueprint (`render.yaml`) configures both:
1. Web service: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. Cron job (`0 */6 * * *`): `python scripts/run_sync.py --triggered-by cron`

---

## Testing

Run the complete automated test suite:

```powershell
venv\Scripts\python -m pytest -q
```

---

## Known Limitations

- **Historical / Sync-based Data**: Statistics reflect matches imported from Cricsheet; real-time ball-by-ball live streaming during ongoing matches is not supported.
- **Player Name Formats**: Cricsheet uses abbreviated canonical names (e.g., `V Kohli`, `RG Sharma`, `JJ Bumrah`). Common full names and dynamic `Initial + Surname` patterns are resolved automatically, though rare multi-initial or single-surname inputs may require the canonical name.
- **Tournament Stage Metadata**: `matches.stage` is `NULL` in currently imported Cricsheet records, so season champions are derived chronologically from each season's final match date (`ORDER BY match_date DESC, match_id DESC`).
- **RAG Knowledge Coverage**: Narrative answers are grounded in ingested documents (`knowledge_base/` + synchronized DB match summaries in `rag_documents`/`rag_chunks`); topics not yet ingested into `rag_documents` return an explicit missing-context notice rather than fabricating facts.
