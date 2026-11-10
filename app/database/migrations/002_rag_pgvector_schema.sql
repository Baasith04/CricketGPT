-- =============================================================================
-- CricketGPT Database Migration 002: Hybrid RAG & pgvector Schema
-- =============================================================================
-- Target Database : Supabase PostgreSQL 15+ with pgvector
-- Embedding Model : Google Gemini gemini-embedding-2 (768 dimensions)
-- Non-destructive : Uses IF NOT EXISTS throughout; preserves all 12 core tables.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- TABLE 13: rag_documents
-- Source-level document registry supporting incremental ingestion and SHA-256
-- duplicate/change detection.
-- =============================================================================
CREATE TABLE IF NOT EXISTS rag_documents (
    doc_id BIGSERIAL PRIMARY KEY,
    source_key VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(300) NOT NULL,
    doc_type VARCHAR(50) NOT NULL CHECK (
        doc_type IN (
            'match_report',
            'season_summary',
            'player_profile',
            'team_history',
            'cricket_rule',
            'general_knowledge'
        )
    ),
    source_path TEXT,
    source_url TEXT,
    content_sha256 VARCHAR(64) NOT NULL,
    season VARCHAR(15),
    match_id INT REFERENCES matches(match_id) ON DELETE SET NULL,
    teams TEXT[] NOT NULL DEFAULT '{}',
    players TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_count INT NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_sha256 ON rag_documents (content_sha256);
CREATE INDEX IF NOT EXISTS idx_rag_documents_doc_type ON rag_documents (doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_documents_season ON rag_documents (season);

COMMENT ON TABLE rag_documents IS 'Source document registry with SHA-256 deduplication and metadata tags for CricketGPT RAG.';


-- =============================================================================
-- TABLE 14: rag_chunks
-- Chunked document segments with 384-d SentenceTransformer embeddings,
-- PostgreSQL tsvector full-text index, and structured metadata filters.
-- =============================================================================
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    doc_id BIGINT NOT NULL REFERENCES rag_documents(doc_id) ON DELETE CASCADE,
    chunk_index INT NOT NULL CHECK (chunk_index >= 0),
    chunk_text TEXT NOT NULL,
    chunk_sha256 VARCHAR(64) NOT NULL,
    token_estimate INT NOT NULL DEFAULT 0 CHECK (token_estimate >= 0),
    doc_type VARCHAR(50) NOT NULL,
    season VARCHAR(15),
    match_id INT REFERENCES matches(match_id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rag_chunks_doc_index UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_tsv
    ON rag_chunks USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_type
    ON rag_chunks (doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_season
    ON rag_chunks (season);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_match_id
    ON rag_chunks (match_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_metadata
    ON rag_chunks USING gin (metadata);

COMMENT ON TABLE rag_chunks IS 'Chunked knowledge passages with Gemini gemini-embedding-2 (768-d) pgvector embeddings and tsvector index.';

