"""
CricketGPT — Hybrid Vector + Keyword Retrieval against Supabase pgvector
"""

import logging
from typing import Any, Dict, List, Optional

from app.database.connection import get_db_connection
from app.rag.embeddings.embedder import get_embedding_service, retry_with_backoff

logger = logging.getLogger(__name__)


def _format_pgvector_literal(embedding: List[float]) -> str:
    """Format a float list into PostgreSQL pgvector literal '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{float(v):.8f}" for v in embedding) + "]"


def hybrid_retrieve(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.25,
    doc_type: Optional[str] = None,
    season: Optional[str] = None,
    match_id: Optional[int] = None,
    team: Optional[str] = None,
    player: Optional[str] = None,
    vector_weight: float = 0.75,
    keyword_weight: float = 0.25,
    embedder=None,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid semantic (pgvector cosine) + keyword (tsvector) retrieval
    over `rag_chunks` joined with `rag_documents`, applying optional metadata filters
    and configurable `top_k` / `similarity_threshold`.
    """
    if not query or not query.strip():
        raise ValueError("Retrieval query cannot be empty.")
    if top_k < 1 or top_k > 50:
        raise ValueError("top_k must be between 1 and 50.")
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0.0 and 1.0.")

    svc = embedder or get_embedding_service()
    query_vector = svc.embed_query(query.strip())
    vec_literal = _format_pgvector_literal(query_vector)

    filter_clauses: List[str] = ["c.embedding IS NOT NULL"]
    filter_params: List[Any] = []

    if doc_type:
        filter_clauses.append("c.doc_type = %s")
        filter_params.append(doc_type.strip())
    if season:
        filter_clauses.append("c.season = %s")
        filter_params.append(season.strip())
    if match_id is not None:
        filter_clauses.append("c.match_id = %s")
        filter_params.append(match_id)
    if team:
        filter_clauses.append(
            "(EXISTS (SELECT 1 FROM unnest(d.teams) t WHERE t ILIKE %s) "
            "OR c.chunk_text ILIKE %s)"
        )
        team_pat = f"%{team.strip()}%"
        filter_params.extend([team_pat, team_pat])
    if player:
        filter_clauses.append(
            "(EXISTS (SELECT 1 FROM unnest(d.players) p WHERE p ILIKE %s) "
            "OR c.chunk_text ILIKE %s)"
        )
        player_pat = f"%{player.strip()}%"
        filter_params.extend([player_pat, player_pat])

    where_sql = ("WHERE " + " AND ".join(filter_clauses)) if filter_clauses else ""

    sql = f"""
        WITH scored AS (
            SELECT
                c.chunk_id,
                c.doc_id,
                d.source_key,
                d.title,
                d.doc_type,
                d.source_path,
                d.source_url,
                c.season,
                c.match_id,
                d.teams,
                d.players,
                c.chunk_index,
                c.chunk_text,
                c.metadata,
                GREATEST(0.0, 1.0 - (c.embedding <=> %s::vector)) AS vector_similarity,
                COALESCE(
                    ts_rank_cd(
                        c.search_tsv,
                        websearch_to_tsquery('english', %s)
                    ),
                    0.0
                ) AS keyword_score
            FROM rag_chunks c
            JOIN rag_documents d ON d.doc_id = c.doc_id
            {where_sql}
        )
        SELECT
            chunk_id,
            doc_id,
            source_key,
            title,
            doc_type,
            source_path,
            source_url,
            season,
            match_id,
            teams,
            players,
            chunk_index,
            chunk_text,
            metadata,
            ROUND(vector_similarity::numeric, 4) AS vector_similarity,
            ROUND(keyword_score::numeric, 4) AS keyword_score,
            ROUND(
                (
                    %s * vector_similarity
                    + %s * LEAST(keyword_score, 1.0)
                )::numeric,
                4
            ) AS hybrid_score
        FROM scored
        WHERE vector_similarity >= %s
           OR keyword_score >= 0.05
        ORDER BY hybrid_score DESC, vector_similarity DESC
        LIMIT %s;
    """

    params: List[Any] = [
        vec_literal,
        query.strip(),
        *filter_params,
        vector_weight,
        keyword_weight,
        similarity_threshold,
        top_k,
    ]

    def _run_query() -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                columns = [col.name for col in cur.description]
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        for r in rows:
            for key in ("vector_similarity", "keyword_score", "hybrid_score"):
                if r.get(key) is not None:
                    r[key] = float(r[key])
        return rows

    return retry_with_backoff(
        _run_query,
        max_attempts=3,
        base_delay=0.3,
        operation_name="pgvector hybrid retrieval",
    )

