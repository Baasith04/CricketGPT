# CricketGPT — RAG (Retrieval-Augmented Generation)

## Responsibility
Provides semantic retrieval over IPL textual knowledge (match narratives, tournament summaries, rules, and editorial content) using Supabase PostgreSQL's `pgvector` extension.

### Core Architecture
1. **Document Ingestion:** Text extraction from tournament reports, rules, and commentary.
2. **Chunking (`chunking/`):** Splits text into semantically cohesive passages with metadata tags (season, match, teams).
3. **Embeddings (`embeddings/`):** Generates high-dimensional vector representations via Gemini embedding models.
4. **Vector Storage:** Stores embeddings in Supabase PostgreSQL using `pgvector` index structures (HNSW / IVFFlat).
5. **Semantic Retrieval (`retrieval/`):** Cosine similarity / vector distance search with metadata pre-filtering.
6. **Pipeline Orchestrator (`pipeline/`):** End-to-end coordination delivering relevant context chunks to the AI answer generator.

