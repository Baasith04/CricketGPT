-- =============================================================================
-- CricketGPT Database Migration 003: Safe Migration to Gemini 768-d Embeddings
-- =============================================================================
-- Non-destructive: Preserves all `rag_documents` and `rag_chunks` rows and
-- metadata while converting `rag_chunks.embedding` from vector(384) to vector(768).
-- Existing 384-d vectors are cleared to NULL so no old SentenceTransformer
-- vectors can remain mixed with Gemini 768-d vectors, then re-embedded via Python.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_rag_chunks_embedding_hnsw;

ALTER TABLE rag_chunks
    ALTER COLUMN embedding DROP NOT NULL;

BEGIN;

-- Remove the old 384-dimensional vector index
DROP INDEX IF EXISTS idx_rag_chunks_embedding_hnsw;

-- Allow temporary NULL embeddings during migration
ALTER TABLE rag_chunks
    ALTER COLUMN embedding DROP NOT NULL;

-- Clear vectors incompatible with the new 768-dimensional model
UPDATE rag_chunks
SET embedding = NULL
WHERE embedding IS NOT NULL
  AND vector_dims(embedding) <> 768;

-- Change the vector column dimension
ALTER TABLE rag_chunks
    ALTER COLUMN embedding TYPE vector(768)
    USING embedding::vector(768);

-- Update table documentation
COMMENT ON TABLE rag_chunks IS
'Chunked knowledge passages with Gemini gemini-embedding-2 768-dimensional embeddings.';

-- Recreate cosine similarity index
CREATE INDEX idx_rag_chunks_embedding_hnsw
ON rag_chunks
USING hnsw (embedding vector_cosine_ops);

COMMIT;
