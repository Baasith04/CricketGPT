"""
CricketGPT — End-to-End Hybrid RAG Ingestion & Generation Pipeline
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from psycopg.types.json import Jsonb

from app.ai.llm.client import generate_response
from app.ai.prompts.system_prompt import CRICKETGPT_SYSTEM_PROMPT
from app.database.connection import get_db_connection
from app.rag.chunking.chunker import (
    compute_sha256,
    extract_text_from_file,
    prepare_document_chunks,
)
from app.rag.embeddings.embedder import (
    DailyQuotaExhaustedError,
    EMBEDDING_DIMENSION,
    REQUIRED_EMBEDDING_MODEL,
    get_embedding_service,
    is_daily_quota_exhausted_error,
    retry_with_backoff,
)
from app.rag.retrieval.hybrid_retriever import (
    _format_pgvector_literal,
    hybrid_retrieve,
)

logger = logging.getLogger(__name__)

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "database"
    / "migrations"
    / "002_rag_pgvector_schema.sql"
)
GEMINI_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "database"
    / "migrations"
    / "003_gemini_embedding_migration.sql"
)


def apply_rag_migration() -> None:
    """Apply the non-destructive pgvector + RAG schema migration safely."""
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    def _exec():
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    retry_with_backoff(_exec, max_attempts=3, base_delay=0.5, operation_name="apply RAG migration")


def apply_gemini_embedding_migration(batch_size: int = 32, embedder=None) -> Dict[str, Any]:
    """
    Safely migrate `rag_chunks.embedding` from vector(384) to vector(768),
    re-embed every existing chunk using Gemini `gemini-embedding-2`,
    restore NOT NULL, and rebuild the HNSW cosine index without dropping rows.
    """
    migration_sql = GEMINI_MIGRATION_PATH.read_text(encoding="utf-8")

    def _run_alter():
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(migration_sql)
            conn.commit()

    retry_with_backoff(
        _run_alter, max_attempts=3, base_delay=0.5, operation_name="apply 003 Gemini migration"
    )

    reembedded = reembed_existing_chunks(batch_size=batch_size, embedder=embedder)

    def _finalize_index():
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rag_chunks WHERE embedding IS NULL;")
                null_count = cur.fetchone()[0]
                if null_count > 0:
                    raise RuntimeError(
                        f"Cannot finalize NOT NULL / HNSW index: {null_count} chunk(s) have NULL embedding."
                    )
                cur.execute("ALTER TABLE rag_chunks ALTER COLUMN embedding SET NOT NULL;")
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw "
                    "ON rag_chunks USING hnsw (embedding vector_cosine_ops);"
                )
            conn.commit()

    retry_with_backoff(
        _finalize_index, max_attempts=3, base_delay=0.5, operation_name="finalize Gemini HNSW index"
    )
    return reembedded


def reembed_existing_chunks(batch_size: int = 32, embedder=None) -> Dict[str, Any]:
    """Re-embed all existing rows in `rag_chunks` using the configured Gemini embedder."""
    svc = embedder or get_embedding_service()

    def _fetch_all_chunks():
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chunk_id, chunk_text FROM rag_chunks ORDER BY chunk_id ASC;")
                return cur.fetchall()

    rows = retry_with_backoff(
        _fetch_all_chunks, max_attempts=3, base_delay=0.3, operation_name="fetch rag_chunks for re-embedding"
    )
    if not rows:
        return {"reembedded_chunks": 0, "model": svc.model_name, "dimension": svc.dimension}

    chunk_ids = [r[0] for r in rows]
    chunk_texts = [r[1] for r in rows]
    vectors = svc.embed_texts(chunk_texts, batch_size=batch_size, task_type="RETRIEVAL_DOCUMENT")

    def _update_chunks():
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for cid, vec in zip(chunk_ids, vectors):
                    cur.execute(
                        "UPDATE rag_chunks SET embedding = %s::vector WHERE chunk_id = %s;",
                        (_format_pgvector_literal(vec), cid),
                    )
            conn.commit()

    retry_with_backoff(
        _update_chunks, max_attempts=3, base_delay=0.5, operation_name="update re-embedded rag_chunks"
    )
    logger.info(
        "Re-embedded %d existing rag_chunks using %s (%d-d).",
        len(chunk_ids),
        svc.model_name,
        svc.dimension,
    )
    return {
        "reembedded_chunks": len(chunk_ids),
        "model": svc.model_name,
        "dimension": svc.dimension,
    }


def _resolve_embedding_provenance(embedder=None) -> tuple[str, int]:
    """Return validated (embedding_model, embedding_dimension) provenance metadata."""
    svc = embedder if embedder is not None else get_embedding_service()
    model_name = getattr(svc, "model_name", None)
    dimension = getattr(svc, "dimension", None)
    if not isinstance(model_name, str) or not model_name.strip():
        model_name = REQUIRED_EMBEDDING_MODEL
    else:
        model_name = model_name.strip()
    if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
        dimension = EMBEDDING_DIMENSION
    return model_name, dimension


def ingest_document(
    source_key: str,
    title: str,
    text: str,
    doc_type: str = "general_knowledge",
    season: Optional[str] = None,
    match_id: Optional[int] = None,
    teams: Optional[List[str]] = None,
    players: Optional[List[str]] = None,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
    force: bool = False,
    embedder=None,
    precomputed_embeddings: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """
    Incrementally ingest one document into `rag_documents` and `rag_chunks`:
    - Computes SHA-256 hash for duplicate/change detection
    - Recursively chunks text and attaches metadata
    - Generates normalized 768-d Gemini embeddings in batch (or validates supplied batch vectors)
    - Atomically replaces chunks only when new or changed (or `force=True`)
    """
    if not source_key or not source_key.strip():
        raise ValueError("source_key cannot be empty.")
    if not text or not text.strip():
        raise ValueError("Document text cannot be empty.")

    content_hash = compute_sha256(text.strip())

    def _check_existing():
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, content_sha256, chunk_count FROM rag_documents WHERE source_key = %s;",
                    (source_key.strip(),),
                )
                return cur.fetchone()

    existing = retry_with_backoff(
        _check_existing, max_attempts=3, base_delay=0.3, operation_name="check rag_documents"
    )
    if existing and existing[1] == content_hash and not force:
        return {
            "source_key": source_key,
            "doc_id": existing[0],
            "status": "unchanged",
            "chunk_count": existing[2],
        }

    embedding_model, embedding_dimension = _resolve_embedding_provenance(embedder)
    doc_meta = dict(extra_metadata or {})
    doc_meta["embedding_model"] = embedding_model
    doc_meta["embedding_dimension"] = embedding_dimension

    chunks = prepare_document_chunks(
        text=text,
        source_key=source_key.strip(),
        title=title.strip(),
        doc_type=doc_type,
        season=season,
        match_id=match_id,
        teams=teams,
        players=players,
        source_path=source_path,
        source_url=source_url,
        extra_metadata=doc_meta,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if precomputed_embeddings is not None:
        if len(precomputed_embeddings) != len(chunks):
            raise ValueError(
                f"Expected {len(chunks)} precomputed embeddings, got {len(precomputed_embeddings)}."
            )
        for idx, vec in enumerate(precomputed_embeddings):
            if len(vec) != embedding_dimension:
                raise ValueError(
                    f"Precomputed embedding dimension mismatch at chunk {idx}: "
                    f"expected {embedding_dimension}, got {len(vec)}."
                )
        embeddings = precomputed_embeddings
    else:
        svc = embedder or get_embedding_service()
        embeddings = svc.embed_texts(
            [c["chunk_text"] for c in chunks],
            task_type="RETRIEVAL_DOCUMENT",
        )

    teams_list = list(teams or [])
    players_list = list(players or [])

    def _write_tx() -> int:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rag_documents (
                        source_key, title, doc_type, source_path, source_url,
                        content_sha256, season, match_id, teams, players,
                        metadata, chunk_count, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, NOW()
                    )
                    ON CONFLICT (source_key) DO UPDATE SET
                        title = EXCLUDED.title,
                        doc_type = EXCLUDED.doc_type,
                        source_path = EXCLUDED.source_path,
                        source_url = EXCLUDED.source_url,
                        content_sha256 = EXCLUDED.content_sha256,
                        season = EXCLUDED.season,
                        match_id = EXCLUDED.match_id,
                        teams = EXCLUDED.teams,
                        players = EXCLUDED.players,
                        metadata = EXCLUDED.metadata,
                        chunk_count = EXCLUDED.chunk_count,
                        updated_at = NOW()
                    RETURNING doc_id;
                    """,
                    (
                        source_key.strip(),
                        title.strip(),
                        doc_type,
                        source_path,
                        source_url,
                        content_hash,
                        season,
                        match_id,
                        teams_list,
                        players_list,
                        Jsonb(doc_meta),
                        len(chunks),
                    ),
                )
                doc_id = cur.fetchone()[0]
                cur.execute("DELETE FROM rag_chunks WHERE doc_id = %s;", (doc_id,))

                for chunk, vec in zip(chunks, embeddings):
                    cur.execute(
                        """
                        INSERT INTO rag_chunks (
                            doc_id, chunk_index, chunk_text, chunk_sha256,
                            token_estimate, doc_type, season, match_id,
                            metadata, embedding
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector);
                        """,
                        (
                            doc_id,
                            chunk["chunk_index"],
                            chunk["chunk_text"],
                            chunk["chunk_sha256"],
                            chunk["token_estimate"],
                            chunk["doc_type"],
                            chunk["season"],
                            chunk["match_id"],
                            Jsonb(chunk["metadata"]),
                            _format_pgvector_literal(vec),
                        ),
                    )
            conn.commit()
        return doc_id

    doc_id = retry_with_backoff(
        _write_tx, max_attempts=3, base_delay=0.5, operation_name="ingest rag document"
    )
    status = "updated" if existing else "ingested"
    logger.info(
        "RAG document %s: source_key=%s doc_id=%d chunks=%d",
        status,
        source_key,
        doc_id,
        len(chunks),
    )
    return {
        "source_key": source_key,
        "doc_id": doc_id,
        "status": status,
        "chunk_count": len(chunks),
    }


def ingest_directory(
    directory: str | Path,
    default_doc_type: str = "general_knowledge",
    force: bool = False,
    embedder=None,
) -> Dict[str, Any]:
    """Batch-ingest all supported documents (.md, .txt, .json, .pdf) inside a directory."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"Knowledge directory not found: {root}")

    supported_exts = {".md", ".markdown", ".txt", ".json", ".pdf"}
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in supported_exts
    )

    counts = {"ingested": 0, "updated": 0, "unchanged": 0, "failed": 0}
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for file_path in files:
        rel_key = file_path.relative_to(root).as_posix()
        try:
            text, meta = extract_text_from_file(file_path)
            if not text:
                continue
            title = str(meta.get("title") or file_path.stem.replace("_", " ").title())
            doc_type = str(meta.get("doc_type") or default_doc_type)
            season = str(meta["season"]) if meta.get("season") is not None else None
            match_id = int(meta["match_id"]) if meta.get("match_id") is not None else None
            teams = meta.get("teams") if isinstance(meta.get("teams"), list) else None
            players = meta.get("players") if isinstance(meta.get("players"), list) else None
            source_url = str(meta["source_url"]) if meta.get("source_url") else None

            outcome = ingest_document(
                source_key=f"file:{rel_key}",
                title=title,
                text=text,
                doc_type=doc_type,
                season=season,
                match_id=match_id,
                teams=teams,
                players=players,
                source_path=str(file_path),
                source_url=source_url,
                extra_metadata={k: v for k, v in meta.items() if k not in {
                    "title", "doc_type", "season", "match_id", "teams", "players", "source_url"
                }},
                force=force,
                embedder=embedder,
            )
            counts[outcome["status"]] += 1
            results.append(outcome)
        except Exception as exc:
            if is_daily_quota_exhausted_error(exc):
                logger.error(
                    "Gemini daily embedding quota exhausted while ingesting %s; stopping directory ingestion.",
                    rel_key,
                )
                raise DailyQuotaExhaustedError(
                    f"Gemini daily embedding quota exhausted while ingesting '{rel_key}': {exc}"
                ) from exc
            counts["failed"] += 1
            errors.append({"file": rel_key, "error": str(exc)})
            logger.error("Failed ingesting %s: %s", rel_key, exc)

    return {
        "directory": str(root),
        "files_scanned": len(files),
        "counts": counts,
        "results": results,
        "errors": errors,
    }


def classify_match_stage(
    stage: Optional[str],
    match_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Classify a match stage strictly from Cricsheet/database metadata without
    guessing finals chronologically.
    """
    clean_stage = stage.strip() if isinstance(stage, str) and stage.strip() else None
    lower = clean_stage.lower() if clean_stage else ""

    if lower == "final":
        return {
            "stage": clean_stage,
            "stage_category": "final",
            "stage_label": "Final",
            "is_season_final": True,
        }

    if clean_stage and any(
        kw in lower for kw in ("qualifier", "eliminator", "semi", "play-off", "playoff")
    ):
        return {
            "stage": clean_stage,
            "stage_category": "playoff",
            "stage_label": clean_stage,
            "is_season_final": False,
        }

    league_label = f"League Match {match_number}" if match_number else "League Match"
    return {
        "stage": clean_stage,
        "stage_category": "league",
        "stage_label": league_label,
        "is_season_final": False,
    }


def ingest_db_match_summaries(
    seasons: Optional[List[str]] = None,
    limit: int = 100,
    force: bool = False,
    embedder=None,
    match_ids: Optional[List[int]] = None,
    batch_embed: bool = False,
    embed_batch_size: int = 32,
) -> Dict[str, Any]:
    """
    Generate and ingest concise, factual match-level summary documents directly
    from Supabase match/innings/award tables (never ball-by-ball deliveries).

    When `match_ids` is supplied (e.g., from incremental Cricsheet sync), ONLY
    those exact match IDs are processed.
    """
    unique_match_ids: Optional[List[int]] = None
    if match_ids is not None:
        unique_match_ids = list(
            dict.fromkeys(
                int(mid) for mid in match_ids
                if isinstance(mid, int) and not isinstance(mid, bool) and mid > 0
            )
        )
        if not unique_match_ids:
            return {
                "processed": 0,
                "counts": {"ingested": 0, "updated": 0, "unchanged": 0, "failed": 0},
                "failed_match_ids": [],
                "errors": [],
            }

    if unique_match_ids is not None:
        where_sql = "WHERE m.match_id = ANY(%s)"
        limit_sql = ""
        params: tuple = (unique_match_ids,)
    elif seasons:
        where_sql = "WHERE m.season = ANY(%s)"
        limit_sql = "LIMIT %s"
        params = (seasons, limit)
    else:
        where_sql = ""
        limit_sql = "LIMIT %s"
        params = (limit,)

    query = f"""
        SELECT
            m.match_id,
            m.season,
            COALESCE(
                m.match_number,
                CASE
                    WHEN (m.raw_json->'info'->'event'->>'match_number') ~ '^\\d+$'
                    THEN (m.raw_json->'info'->'event'->>'match_number')::INT
                    ELSE NULL
                END
            ) AS match_number,
            COALESCE(m.stage, m.raw_json->'info'->'event'->>'stage') AS stage,
            m.match_date,
            m.venue,
            m.city,
            m.result_type,
            m.result_method,
            m.win_by_runs,
            m.win_by_wickets,
            t_toss.canonical_name AS toss_winner,
            m.toss_decision,
            t_win.canonical_name AS winner,
            m.raw_json->'info'->'outcome'->>'eliminator' AS eliminator_winner,
            (
                SELECT STRING_AGG(t.canonical_name, ' vs ' ORDER BY mt.team_number)
                FROM match_teams mt
                JOIN teams t ON t.team_id = mt.team_id
                WHERE mt.match_id = m.match_id
            ) AS teams_label,
            (
                SELECT ARRAY_AGG(t.canonical_name ORDER BY mt.team_number)
                FROM match_teams mt
                JOIN teams t ON t.team_id = mt.team_id
                WHERE mt.match_id = m.match_id
            ) AS teams_arr,
            (
                SELECT STRING_AGG(
                    bt.canonical_name || ' scored ' || i.total_runs || '/' || i.total_wickets ||
                    ' (' || (i.legal_balls_bowled / 6) || '.' || (i.legal_balls_bowled %% 6) || ' overs)',
                    '; ' ORDER BY i.innings_number
                )
                FROM innings i
                JOIN teams bt ON bt.team_id = i.batting_team_id
                WHERE i.match_id = m.match_id AND i.is_super_over = FALSE
            ) AS innings_summary,
            (
                SELECT STRING_AGG(COALESCE(p.canonical_name, ma.recipient_name), ', ')
                FROM match_awards ma
                LEFT JOIN players p ON p.player_id = ma.player_id
                WHERE ma.match_id = m.match_id
            ) AS potm
        FROM matches m
        LEFT JOIN teams t_toss ON t_toss.team_id = m.toss_winner_id
        LEFT JOIN teams t_win ON t_win.team_id = m.winner_id
        {where_sql}
        ORDER BY m.match_date DESC, m.match_id DESC
        {limit_sql};
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    counts = {"ingested": 0, "updated": 0, "unchanged": 0, "failed": 0}
    failed_match_ids: List[int] = []
    errors: List[Dict[str, Any]] = []
    prepared_docs: List[Dict[str, Any]] = []

    embedding_model, embedding_dimension = _resolve_embedding_provenance(embedder)

    for row in rows:
        match_id = row["match_id"]
        season = row["season"]
        stage_info = classify_match_stage(
            stage=row.get("stage"),
            match_number=row.get("match_number"),
        )
        is_final = stage_info["is_season_final"]
        stage_category = stage_info["stage_category"]
        stage_label = stage_info["stage_label"]
        teams_label = row.get("teams_label") or f"Match {match_id}"

        winner = row["winner"] or row["eliminator_winner"]
        margin = (
            f"by {row['win_by_runs']} runs"
            if row["win_by_runs"]
            else (
                f"by {row['win_by_wickets']} wickets"
                if row["win_by_wickets"]
                else (
                    "via Super Over"
                    if row["eliminator_winner"]
                    else "with no result"
                )
            )
        )

        if is_final:
            title = f"IPL {season} Final Match Report: {teams_label}"
        elif stage_category == "playoff":
            title = f"IPL {season} {stage_label} Match Report (Match {match_id}): {teams_label}"
        else:
            title = f"IPL {season} Match {match_id}: {teams_label}"

        venue_text = row.get("venue") or "Unknown"
        city_text = row.get("city") or ""
        city_suffix = (
            f", {city_text}"
            if city_text and city_text.lower() not in venue_text.lower()
            else ""
        )
        body = (
            f"{title} ({stage_label}) was played on {row['match_date']} at {venue_text}"
            f"{city_suffix}.\n\n"
            f"Toss: {row['toss_winner'] or 'Unknown'} won the toss and elected to {row['toss_decision'] or 'play'}.\n"
            f"Innings Summary: {row['innings_summary'] or 'Not recorded'}.\n"
            f"Outcome: {winner or 'No team'} won {margin}"
            f"{(' (' + row['result_method'] + ')') if row['result_method'] else ''}.\n"
            f"Player of the Match: {row['potm'] or 'Not recorded'}.\n"
            f"Database Verification: Derived from Cricsheet match_id {match_id} in CricketGPT Supabase."
        )
        doc_payload = {
            "source_key": f"db:match:{match_id}",
            "title": title,
            "text": body,
            "doc_type": "match_report",
            "season": season,
            "match_id": match_id,
            "teams": row["teams_arr"] or [],
            "source_path": f"supabase://matches/{match_id}",
            "extra_metadata": {
                "stage": stage_info["stage"],
                "stage_category": stage_category,
                "stage_label": stage_label,
                "match_number": row.get("match_number"),
                "is_season_final": is_final,
                "generated_from": "cricsheet_sql",
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension,
            },
        }
        prepared_docs.append(doc_payload)

    if batch_embed and prepared_docs:
        source_keys = [d["source_key"] for d in prepared_docs]
        existing_hashes: Dict[str, str] = {}
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source_key, content_sha256 FROM rag_documents WHERE source_key = ANY(%s);",
                    (source_keys,),
                )
                existing_hashes = {r[0]: r[1] for r in cur.fetchall()}

        docs_to_embed: List[Dict[str, Any]] = []
        chunk_slices: List[tuple] = []
        flat_chunk_texts: List[str] = []

        for d in prepared_docs:
            content_hash = compute_sha256(d["text"].strip())
            if not force and existing_hashes.get(d["source_key"]) == content_hash:
                counts["unchanged"] += 1
                continue
            chunks = prepare_document_chunks(
                text=d["text"],
                source_key=d["source_key"],
                title=d["title"],
                doc_type=d["doc_type"],
                season=d["season"],
                match_id=d["match_id"],
                teams=d["teams"],
                source_path=d["source_path"],
                extra_metadata=d["extra_metadata"],
            )
            start_idx = len(flat_chunk_texts)
            flat_chunk_texts.extend(c["chunk_text"] for c in chunks)
            end_idx = len(flat_chunk_texts)
            docs_to_embed.append(d)
            chunk_slices.append((start_idx, end_idx))

        batch_vectors: Optional[List[List[float]]] = None
        if flat_chunk_texts:
            try:
                svc = embedder or get_embedding_service()
                batch_vectors = svc.embed_texts(
                    flat_chunk_texts,
                    batch_size=embed_batch_size,
                    task_type="RETRIEVAL_DOCUMENT",
                )
            except Exception as batch_exc:
                if is_daily_quota_exhausted_error(batch_exc):
                    logger.error(
                        "Gemini daily embedding quota exhausted during batch embedding; "
                        "stopping immediately without per-document fallback."
                    )
                    raise DailyQuotaExhaustedError(str(batch_exc)) from batch_exc
                logger.warning(
                    "Batch Gemini embedding failed (%s); falling back to per-document ingestion.",
                    batch_exc,
                )
                batch_vectors = None

        doc_items = [
            (d, batch_vectors[s_idx:e_idx] if batch_vectors is not None else None)
            for d, (s_idx, e_idx) in zip(docs_to_embed, chunk_slices)
        ]
    else:
        doc_items = [(d, None) for d in prepared_docs]

    for d, pre_vecs in doc_items:
        try:
            outcome = ingest_document(
                **d,
                force=force,
                embedder=embedder,
                precomputed_embeddings=pre_vecs,
            )
            counts[outcome["status"]] += 1
        except Exception as exc:
            if is_daily_quota_exhausted_error(exc):
                logger.error(
                    "Gemini daily embedding quota exhausted at match %s; stopping immediately.",
                    d["match_id"],
                )
                raise DailyQuotaExhaustedError(str(exc)) from exc
            counts["failed"] += 1
            failed_match_ids.append(d["match_id"])
            errors.append({"match_id": d["match_id"], "error": str(exc)})
            logger.error("Failed ingesting RAG match summary for match %s: %s", d["match_id"], exc)

    return {
        "processed": len(rows),
        "counts": counts,
        "failed_match_ids": failed_match_ids,
        "errors": errors,
    }


def _build_backfill_resume_command(
    batch_size: int = 50,
    seasons: Optional[List[str]] = None,
    max_matches: Optional[int] = None,
    force: bool = False,
) -> str:
    """Build exact CLI command to resume missing historical RAG backfill."""
    parts = ["python", "scripts/ingest_rag.py", "--backfill-rag"]
    if batch_size != 50:
        parts.extend(["--batch-size", str(batch_size)])
    if seasons:
        parts.append("--seasons")
        parts.extend(str(s) for s in seasons)
    if max_matches is not None:
        parts.extend(["--max-matches", str(max_matches)])
    if force:
        parts.append("--force")
    return " ".join(parts)


def backfill_historical_match_rag(
    batch_size: int = 50,
    seasons: Optional[List[str]] = None,
    max_matches: Optional[int] = None,
    include_existing: bool = False,
    force: bool = False,
    dry_run: bool = False,
    embedder=None,
) -> Dict[str, Any]:
    """
    Safely backfill `rag_documents` and `rag_chunks` for stored Supabase IPL matches
    in configurable batches using `ingest_db_match_summaries`.

    Resumable by design: when `include_existing=False` (default), it queries only
    matches lacking `db:match:<match_id>` so re-running after an interruption resumes
    automatically without regenerating or deleting existing RAG documents.
    Stops immediately on Gemini daily quota exhaustion without repeated retries.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    clauses: List[str] = []
    params: List[Any] = []
    if not include_existing:
        clauses.append("d.doc_id IS NULL")
    if seasons:
        clauses.append("m.season = ANY(%s)")
        params.append(seasons)

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM matches;")
            total_sql_matches = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*)
                FROM matches m
                JOIN rag_documents d ON d.source_key = 'db:match:' || m.match_id::text;
                """
            )
            already_covered = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT m.match_id
                FROM matches m
                LEFT JOIN rag_documents d
                  ON d.source_key = 'db:match:' || m.match_id::text
                {where_sql}
                ORDER BY m.season ASC, m.match_date ASC, m.match_id ASC;
                """,
                tuple(params),
            )
            target_ids = [r[0] for r in cur.fetchall()]

    if max_matches is not None and max_matches >= 0:
        target_ids = target_ids[:max_matches]

    resume_cmd = _build_backfill_resume_command(
        batch_size=batch_size,
        seasons=seasons,
        max_matches=max_matches,
        force=force,
    )
    active_model = embedder.model_name if embedder is not None else REQUIRED_EMBEDDING_MODEL

    if dry_run:
        return {
            "dry_run": True,
            "embedding_model": active_model,
            "total_sql_matches": total_sql_matches,
            "already_covered": already_covered,
            "missing_matches": max(0, total_sql_matches - already_covered),
            "target_count": len(target_ids),
            "batch_size": batch_size,
            "sample_target_ids": target_ids[:10],
            "resume_command": resume_cmd if target_ids else None,
        }

    totals = {"processed": 0, "ingested": 0, "updated": 0, "unchanged": 0, "failed": 0}
    all_failed_ids: List[int] = []
    all_errors: List[Dict[str, Any]] = []
    quota_exhausted = False
    stopped_reason: Optional[str] = None
    batches_executed = 0

    total_batches = (len(target_ids) + batch_size - 1) // batch_size if target_ids else 0
    for idx in range(0, len(target_ids), batch_size):
        batch_num = (idx // batch_size) + 1
        batch_ids = target_ids[idx : idx + batch_size]
        try:
            res = ingest_db_match_summaries(
                match_ids=batch_ids,
                force=force,
                embedder=embedder,
                batch_embed=True,
            )
        except Exception as exc:
            if is_daily_quota_exhausted_error(exc):
                quota_exhausted = True
                stopped_reason = "daily_quota_exhausted"
                all_failed_ids.extend(batch_ids)
                all_errors.append(
                    {
                        "batch": batch_num,
                        "match_ids": list(batch_ids),
                        "reason": "daily_quota_exhausted",
                        "error": str(exc),
                    }
                )
                logger.error(
                    "Backfill batch %d/%d stopped immediately on Gemini daily quota exhaustion: %s",
                    batch_num,
                    total_batches,
                    exc,
                )
                break
            raise

        batches_executed += 1
        totals["processed"] += res["processed"]
        for key in ("ingested", "updated", "unchanged", "failed"):
            totals[key] += res["counts"][key]
        all_failed_ids.extend(res.get("failed_match_ids", []))
        all_errors.extend(res.get("errors", []))
        logger.info(
            "Backfill batch %d/%d: processed=%d ingested=%d updated=%d unchanged=%d failed=%d",
            batch_num,
            total_batches,
            res["processed"],
            res["counts"]["ingested"],
            res["counts"]["updated"],
            res["counts"]["unchanged"],
            res["counts"]["failed"],
        )
        if res.get("quota_exhausted"):
            quota_exhausted = True
            stopped_reason = "daily_quota_exhausted"
            break

    completed_count = totals["ingested"] + totals["updated"] + totals["unchanged"]
    remaining_matches = max(0, len(target_ids) - completed_count)

    return {
        "dry_run": False,
        "status": "stopped_quota_exhausted" if quota_exhausted else "completed",
        "quota_exhausted": quota_exhausted,
        "stopped_reason": stopped_reason,
        "embedding_model": active_model,
        "total_sql_matches": total_sql_matches,
        "previously_covered": already_covered,
        "target_count": len(target_ids),
        "batches_executed": batches_executed,
        "remaining_matches": remaining_matches,
        "resume_command": resume_cmd if (quota_exhausted or remaining_matches > 0) else None,
        "counts": totals,
        "failed_match_ids": all_failed_ids,
        "errors": all_errors,
    }


def _format_sources_footer(chunks: List[Dict[str, Any]], has_sql: bool) -> str:
    """Build deterministic source attribution footer for RAG / Hybrid responses."""
    lines = ["", "### Sources"]
    if has_sql:
        lines.append("- **[SQL]** CricketGPT PostgreSQL / Supabase (verified delivery & match statistics)")
    for idx, ch in enumerate(chunks, start=1):
        meta_bits = [ch.get("doc_type", "document")]
        if ch.get("season"):
            meta_bits.append(f"IPL {ch['season']}")
        if ch.get("match_id"):
            meta_bits.append(f"Match {ch['match_id']}")
        loc = ch.get("source_url") or ch.get("source_path") or ch.get("source_key")
        lines.append(
            f"- **[S{idx}] {ch['title']}** ({', '.join(meta_bits)}; "
            f"score: {ch.get('hybrid_score', 0):.3f}; source: `{loc}`)"
        )
    return "\n".join(lines)


def answer_rag_question(
    question: str,
    sql_context: Optional[str] = None,
    top_k: int = 5,
    similarity_threshold: float = 0.20,
    doc_type: Optional[str] = None,
    season: Optional[str] = None,
    match_id: Optional[int] = None,
    team: Optional[str] = None,
    player: Optional[str] = None,
    embedder=None,
) -> str:
    """
    Answer narrative or hybrid SQL+RAG questions:
    1. Retrieve top-k chunks using pgvector cosine + tsvector hybrid search
    2. Combine retrieved passages with optional verified SQL statistics
    3. Generate a grounded response via multi-provider LLM fallback with citations
    """
    if not question or not question.strip():
        return "Please enter a cricket question."

    chunks = hybrid_retrieve(
        query=question,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        doc_type=doc_type,
        season=season,
        match_id=match_id,
        team=team,
        player=player,
        embedder=embedder,
    )

    if not chunks and not sql_context:
        return (
            "I could not find relevant documents in the CricketGPT knowledge base "
            "to answer this question accurately. Please ingest relevant source documents "
            "or ask a statistical IPL question."
        )

    context_blocks: List[str] = []
    if sql_context:
        context_blocks.append(f"[SQL] Verified Database Statistics:\n{sql_context}")

    for idx, ch in enumerate(chunks, start=1):
        context_blocks.append(
            f"[S{idx}] Title: {ch['title']} | Type: {ch['doc_type']}"
            f"{(' | Season: ' + str(ch['season'])) if ch.get('season') else ''}\n"
            f"{ch['chunk_text']}"
        )

    assembled_context = "\n\n---\n\n".join(context_blocks)

    prompt = f"""
{CRICKETGPT_SYSTEM_PROMPT}

You are answering in Hybrid RAG mode. Follow these grounding rules strictly:
1. Base all factual claims ONLY on the supplied [SQL] statistics and [S1], [S2]... knowledge chunks below.
2. When citing statistics, rely on [SQL] as authoritative. Never invent runs, wickets, dates, or quotes.
3. Cite sources inline using [SQL] and/or [S1], [S2], etc.
4. If the retrieved context does not cover part of the question, state clearly what is missing.

Supplied Context:
{assembled_context}

User Question:
{question}
"""

    answer_text = generate_response(prompt)
    footer = _format_sources_footer(chunks, has_sql=bool(sql_context))
    return f"{answer_text.strip()}\n{footer}"

