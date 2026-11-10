"""Tests for API rate limiting (multi-worker/Redis) and RAG validation bounds."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.api.rate_limit import (
    RedisFixedWindowBackend,
    SQLiteFixedWindowBackend,
    get_client_ip,
    parse_rate_limit,
    reset_rate_limiter,
    resolve_storage_uri,
)
from app.main import app
from app.rag.embeddings.embedder import DailyQuotaExhaustedError


@pytest.fixture
def client():
    reset_rate_limiter()
    with TestClient(app) as c:
        yield c
    reset_rate_limiter()


def test_parse_rate_limit_valid_and_invalid():
    assert parse_rate_limit("20/minute") == (20, 60)
    assert parse_rate_limit("60/min") == (60, 60)
    assert parse_rate_limit("5/second") == (5, 1)
    assert parse_rate_limit("100/hour") == (100, 3600)
    with pytest.raises(ValueError):
        parse_rate_limit("0/minute")
    with pytest.raises(ValueError):
        parse_rate_limit("invalid")


def test_sqlite_rate_limit_backend_shares_counts_across_worker_instances(tmp_path: Path):
    db_file = tmp_path / "shared_rl.sqlite3"
    worker_one = SQLiteFixedWindowBackend(db_file)
    worker_two = SQLiteFixedWindowBackend(db_file)

    r1 = worker_one.increment("chat:1.2.3.4", limit=2, window_seconds=60)
    r2 = worker_two.increment("chat:1.2.3.4", limit=2, window_seconds=60)
    r3 = worker_one.increment("chat:1.2.3.4", limit=2, window_seconds=60)

    assert r1.allowed is True
    assert r1.remaining == 1
    assert r2.allowed is True
    assert r2.remaining == 0
    assert r3.allowed is False
    assert r3.remaining == 0


def test_resolve_storage_uri_prefers_explicit_or_redis_url(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_STORAGE_URI", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://cache.internal:6379/0")
    assert resolve_storage_uri() == "redis://cache.internal:6379/0"

    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    assert resolve_storage_uri() == "memory://"


def _fake_request(peer_host: str | None, headers: dict[str, str] | None = None):
    client = SimpleNamespace(host=peer_host) if peer_host is not None else None
    normalized_headers = {k.lower(): v for k, v in (headers or {}).items()}
    return SimpleNamespace(client=client, headers=normalized_headers)


def test_get_client_ip_ignores_spoofed_headers_from_untrusted_direct_peer(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    monkeypatch.setenv("RENDER", "true")

    # Public/untrusted direct peer spoofing X-Forwarded-For must not be trusted
    req = _fake_request("203.0.113.5", {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "203.0.113.5"

    # Untrusted peer without proxy env vars must ignore X-Forwarded-For
    monkeypatch.delenv("RENDER", raising=False)
    req_local = _fake_request("10.0.0.5", {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req_local) == "10.0.0.5"


def test_get_client_ip_strips_spoofed_leftmost_and_trusted_hops_under_render(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    monkeypatch.setenv("RENDER", "true")

    # Attacker spoofed leftmost "1.1.1.1"; Render edge proxy appended real client + internal hop
    req = _fake_request("10.10.0.8", {"X-Forwarded-For": "1.1.1.1, 198.51.100.42, 172.16.0.12"})
    assert get_client_ip(req) == "198.51.100.42"

    # Single valid client hop behind trusted proxy
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    req_single = _fake_request("10.1.2.3", {"X-Forwarded-For": "198.51.100.77"})
    assert get_client_ip(req_single) == "198.51.100.77"

    # Malformed rightmost hop falls back safely to verified peer IP
    req_malformed = _fake_request("10.1.2.3", {"X-Forwarded-For": "198.51.100.77, garbage-hop"})
    assert get_client_ip(req_malformed) == "10.1.2.3"


def test_get_client_ip_handles_missing_headers_and_direct_requests(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    monkeypatch.setenv("RENDER", "true")

    # Missing X-Forwarded-For behind proxy falls back to peer IP
    assert get_client_ip(_fake_request("10.1.2.3", {})) == "10.1.2.3"

    # Direct request without forwarded headers uses peer IP
    assert get_client_ip(_fake_request("203.0.113.99", {})) == "203.0.113.99"

    # Missing client object falls back to "unknown"
    assert get_client_ip(_fake_request(None, {"X-Forwarded-For": "198.51.100.1"})) == "unknown"


@patch("app.api.routes.chat.route_question", return_value="Mocked answer")
def test_spoofed_forwarded_for_cannot_bypass_chat_rate_limit(mock_route, client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    reset_rate_limiter()

    r1 = client.post("/api/chat", json={"question": "Q1"}, headers={"X-Forwarded-For": "1.1.1.1"})
    r2 = client.post("/api/chat", json={"question": "Q2"}, headers={"X-Forwarded-For": "2.2.2.2"})
    r3 = client.post("/api/chat", json={"question": "Q3"}, headers={"X-Forwarded-For": "3.3.3.3"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


@patch("app.api.routes.chat.route_question", return_value="Mocked answer")
def test_chat_endpoint_rate_limited_returns_429(mock_route, client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    reset_rate_limiter()

    headers = {"X-Forwarded-For": "198.51.100.10"}
    r1 = client.post("/api/chat", json={"question": "Who won IPL 2024?"}, headers=headers)
    r2 = client.post("/api/chat", json={"question": "Who won IPL 2025?"}, headers=headers)
    r3 = client.post("/api/chat", json={"question": "Who won IPL 2026?"}, headers=headers)

    assert r1.status_code == 200
    assert r1.headers.get("X-RateLimit-Limit") == "2"
    assert r1.headers.get("X-RateLimit-Remaining") == "1"
    assert r2.status_code == 200
    assert r2.headers.get("X-RateLimit-Remaining") == "0"
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    assert "Rate limit exceeded" in r3.json()["detail"]


@patch("app.api.routes.rag.hybrid_retrieve", return_value=[])
def test_rag_search_endpoint_rate_limited_returns_429(mock_retrieve, client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("RATE_LIMIT_RAG_SEARCH", "2/minute")
    reset_rate_limiter()

    headers = {"X-Forwarded-For": "198.51.100.20"}
    assert client.get("/api/rag/search?q=DLS%20rules", headers=headers).status_code == 200
    assert client.get("/api/rag/search?q=DLS%20rules", headers=headers).status_code == 200
    r3 = client.get("/api/rag/search?q=DLS%20rules", headers=headers)
    assert r3.status_code == 429


@patch("app.api.routes.rag.ingest_document", return_value={
    "source_key": "file:test.md", "doc_id": 1, "status": "ingested", "chunk_count": 1
})
def test_rag_ingest_endpoint_rate_limited_and_preserves_auth(mock_ingest, client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("RATE_LIMIT_RAG_INGEST", "2/minute")
    monkeypatch.setenv("INGESTION_API_KEY", "secret-token")
    reset_rate_limiter()

    payload = {"source_key": "k", "title": "Title", "text": "Valid cricket knowledge content."}
    headers = {"Authorization": "Bearer secret-token", "X-Forwarded-For": "198.51.100.30"}

    assert client.post("/api/rag/ingest", json=payload, headers=headers).status_code == 200
    assert client.post("/api/rag/ingest", json=payload, headers=headers).status_code == 200
    assert client.post("/api/rag/ingest", json=payload, headers=headers).status_code == 429


@patch("app.api.routes.rag.hybrid_retrieve", return_value=[])
def test_rag_search_query_exceeding_max_length_returns_422(mock_retrieve, client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    r = client.get(f"/api/rag/search?q={'a' * 501}")
    assert r.status_code == 422


def test_rag_ingest_text_exceeding_max_length_returns_422(client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("INGESTION_API_KEY", "secret-token")
    r = client.post(
        "/api/rag/ingest",
        headers={"Authorization": "Bearer secret-token"},
        json={"source_key": "k", "title": "Long Doc", "text": "x" * 50001},
    )
    assert r.status_code == 422


@patch("app.api.routes.rag.ingest_document")
def test_rag_ingest_503_does_not_leak_upstream_secret(mock_ingest, client: TestClient, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("INGESTION_API_KEY", "secret-token")
    mock_ingest.side_effect = DailyQuotaExhaustedError("raw upstream secret=AIzaLeak")

    r = client.post(
        "/api/rag/ingest",
        headers={"Authorization": "Bearer secret-token"},
        json={"source_key": "k", "title": "Title", "text": "Valid cricket knowledge text."},
    )
    assert r.status_code == 503
    assert "AIzaLeak" not in r.text
    assert "daily embedding quota exhausted" in r.json()["detail"].lower()


@patch.object(RedisFixedWindowBackend, "increment", side_effect=ConnectionError("Redis offline"))
@patch("app.api.routes.chat.route_question", return_value="Fallback OK")
def test_redis_rate_limit_failure_falls_back_to_sqlite(mock_route, mock_redis, client: TestClient, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("RATE_LIMIT_CHAT", "5/minute")
    reset_rate_limiter()

    r = client.post("/api/chat", json={"question": "Who won IPL 2024?"})
    assert r.status_code == 200
    assert r.json()["answer"] == "Fallback OK"

