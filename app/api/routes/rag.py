"""Protected RAG document ingestion and semantic search endpoints."""

import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.rate_limit import rate_limit_rag_ingest, rate_limit_rag_search
from app.database.connection import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
)
from app.rag.embeddings.embedder import DailyQuotaExhaustedError
from app.rag.pipeline.rag_pipeline import (
    ingest_db_match_summaries,
    ingest_directory,
    ingest_document,
)
from app.rag.retrieval.hybrid_retriever import hybrid_retrieve
from app.schemas.rag import (
    RagDirectoryIngestRequest,
    RagIngestRequest,
    RagIngestResponse,
    RagMatchSummariesIngestRequest,
    RagSearchResponse,
)

router = APIRouter(prefix="/api/rag", tags=["RAG"])


def require_ingestion_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None),
) -> None:
    """
    Protect write/ingestion endpoints using INGESTION_API_KEY.
    Accepts either `X-API-Key: <token>` or `Authorization: Bearer <token>`.
    """
    expected = os.getenv("INGESTION_API_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion API key is not configured on the server.",
        )

    provided = (x_api_key or "").strip()
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()

    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ingestion authentication credentials.",
        )

    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid ingestion API key.",
        )


@router.post(
    "/ingest",
    response_model=RagIngestResponse,
    dependencies=[Depends(rate_limit_rag_ingest), Depends(require_ingestion_api_key)],
    summary="Ingest a single knowledge document into pgvector",
)
def ingest_single_document(request: RagIngestRequest) -> RagIngestResponse:
    try:
        result = ingest_document(
            source_key=request.source_key,
            title=request.title,
            text=request.text,
            doc_type=request.doc_type,
            season=request.season,
            match_id=request.match_id,
            teams=request.teams,
            players=request.players,
            source_path=request.source_path,
            source_url=request.source_url,
            extra_metadata=request.extra_metadata,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            force=request.force,
        )
        return RagIngestResponse(**result)
    except DailyQuotaExhaustedError:
        raise HTTPException(
            status_code=503,
            detail="Gemini daily embedding quota exhausted. Please retry after quota recovery.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(status_code=500, detail="Database service unavailable.")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to ingest document.")


@router.post(
    "/ingest/directory",
    dependencies=[Depends(rate_limit_rag_ingest), Depends(require_ingestion_api_key)],
    summary="Batch-ingest documents from a directory",
)
def ingest_directory_endpoint(request: RagDirectoryIngestRequest):
    try:
        return ingest_directory(
            directory=request.directory,
            default_doc_type=request.default_doc_type,
            force=request.force,
        )
    except DailyQuotaExhaustedError:
        raise HTTPException(
            status_code=503,
            detail="Gemini daily embedding quota exhausted. Please retry after quota recovery.",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(status_code=500, detail="Database service unavailable.")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to ingest directory.")


@router.post(
    "/ingest/match-summaries",
    dependencies=[Depends(rate_limit_rag_ingest), Depends(require_ingestion_api_key)],
    summary="Generate and ingest verified match summaries from Supabase",
)
def ingest_match_summaries_endpoint(request: RagMatchSummariesIngestRequest):
    try:
        return ingest_db_match_summaries(
            seasons=request.seasons,
            limit=request.limit,
            force=request.force,
            match_ids=request.match_ids,
        )
    except DailyQuotaExhaustedError:
        raise HTTPException(
            status_code=503,
            detail="Gemini daily embedding quota exhausted. Please retry after quota recovery.",
        )
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(status_code=500, detail="Database service unavailable.")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to ingest match summaries.")


@router.get(
    "/search",
    response_model=RagSearchResponse,
    dependencies=[Depends(rate_limit_rag_search)],
    summary="Run hybrid vector + keyword retrieval",
)
def search_rag_knowledge(
    q: str = Query(..., min_length=2, max_length=500, description="Natural-language search query"),
    top_k: int = Query(default=5, ge=1, le=50),
    similarity_threshold: float = Query(default=0.2, ge=0.0, le=1.0),
    doc_type: Optional[str] = Query(default=None, max_length=50),
    season: Optional[str] = Query(default=None, max_length=15),
    match_id: Optional[int] = Query(default=None, ge=1),
    team: Optional[str] = Query(default=None, max_length=100),
    player: Optional[str] = Query(default=None, max_length=100),
) -> RagSearchResponse:
    try:
        rows = hybrid_retrieve(
            query=q,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            doc_type=doc_type,
            season=season,
            match_id=match_id,
            team=team,
            player=player,
        )
        return RagSearchResponse(
            query=q,
            total_results=len(rows),
            results=rows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (DatabaseConnectionError, DatabaseConfigurationError):
        raise HTTPException(status_code=500, detail="Database service unavailable.")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to perform RAG search.")

