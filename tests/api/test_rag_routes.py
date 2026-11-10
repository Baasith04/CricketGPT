"""API tests for protected RAG ingestion and search endpoints."""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ingest_unconfigured_key_returns_503(client: TestClient):
    with patch.dict("os.environ", {"INGESTION_API_KEY": ""}, clear=False):
        r = client.post(
            "/api/rag/ingest",
            json={"source_key": "k", "title": "t", "text": "Some valid text content here."},
        )
    assert r.status_code == 503


def test_ingest_missing_auth_header_returns_401(client: TestClient):
    with patch.dict("os.environ", {"INGESTION_API_KEY": "secret-token"}):
        r = client.post(
            "/api/rag/ingest",
            json={"source_key": "k", "title": "t", "text": "Some valid text content here."},
        )
    assert r.status_code == 401


def test_ingest_wrong_api_key_returns_403(client: TestClient):
    with patch.dict("os.environ", {"INGESTION_API_KEY": "secret-token"}):
        r = client.post(
            "/api/rag/ingest",
            headers={"X-API-Key": "wrong-token"},
            json={"source_key": "k", "title": "t", "text": "Some valid text content here."},
        )
    assert r.status_code == 403


@patch("app.api.routes.rag.ingest_document")
def test_ingest_authorized_succeeds(mock_ingest, client: TestClient):
    mock_ingest.return_value = {
        "source_key": "file:dls.md",
        "doc_id": 1,
        "status": "ingested",
        "chunk_count": 2,
    }
    with patch.dict("os.environ", {"INGESTION_API_KEY": "secret-token"}):
        r = client.post(
            "/api/rag/ingest",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "source_key": "file:dls.md",
                "title": "DLS Rules",
                "text": "Duckworth-Lewis-Stern calculates revised targets.",
                "doc_type": "cricket_rule",
            },
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ingested"
    assert r.json()["chunk_count"] == 2


@patch("app.api.routes.rag.hybrid_retrieve")
def test_rag_search_endpoint_returns_chunks(mock_retrieve, client: TestClient):
    mock_retrieve.return_value = [
        {
            "chunk_id": 1,
            "doc_id": 10,
            "source_key": "file:dls.md",
            "title": "DLS Rules",
            "doc_type": "cricket_rule",
            "season": None,
            "match_id": None,
            "teams": [],
            "players": [],
            "chunk_index": 0,
            "chunk_text": "DLS target calculation...",
            "vector_similarity": 0.85,
            "keyword_score": 0.4,
            "hybrid_score": 0.74,
        }
    ]
    r = client.get("/api/rag/search?q=DLS%20rules&top_k=3&doc_type=cricket_rule")
    assert r.status_code == 200
    data = r.json()
    assert data["total_results"] == 1
    assert data["results"][0]["title"] == "DLS Rules"

