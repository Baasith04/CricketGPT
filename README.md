# CricketGPT Backend

AI-powered IPL cricket statistics and question-answering assistant.

## Overview

CricketGPT maintains its own automatically updated IPL cricket database
using data from Cricsheet, reducing dependence on LLM training-data cutoffs.

## Technology Stack

- **Python** — Programming language
- **FastAPI** — Web framework
- **Uvicorn** — ASGI server
- **Supabase PostgreSQL** — Database (Phase 2)
- **Google Gemini** — AI/LLM (Phase 5)
- **pgvector** — Vector search (Phase 5)

## Quick Start

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt

# Run the development server
python -m uvicorn app.main:app --reload

# Run tests
python -m pytest tests/ -v
```

## API Documentation

Once the server is running, open Swagger UI at:
http://127.0.0.1:8000/docs

## Project Status

- [x] Stage 1 — Project setup and FastAPI basics
- [ ] Stage 2 — Supabase database
- [ ] Stage 3 — Cricsheet data engine
- [ ] Stage 4 — Cricket statistics APIs
- [ ] Stage 5 — Gemini and RAG
- [ ] Stage 6 — Testing and deployment
- [ ] Stage 7 — Frontend

