# CricketGPT — Semantic Retrieval

## Responsibility
Executes nearest-neighbor vector similarity queries against pgvector in Supabase PostgreSQL.

### Query Features
- Cosine similarity: `1 - (embedding <=> query_embedding)`
- Metadata filtering: Filter by season, team, or document type before or during vector ranking.
- Hybrid search: Combines full-text search (`tsvector`) with semantic vector similarity for high-precision retrieval.
- Top-k selection: Retrieves the most relevant $k$ passages with a minimum similarity threshold.

