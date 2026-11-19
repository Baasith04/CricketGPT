"""
Stage 2 Authentication Tests for CricketGPT

Validates:
1. POST /api/chat without token returns HTTP 401.
2. POST /api/chat with invalid/expired/untrusted token returns HTTP 401.
3. POST /api/chat with valid Supabase token reaches the existing chat handler (HTTP 200).
4. Public cricket statistics endpoints remain accessible without authentication.
5. Ingestion endpoints continue to enforce INGESTION_API_KEY authentication.
"""

import time
import uuid
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ec
import jwt
import pytest
from starlette.testclient import TestClient

from app.api.rate_limit import reset_rate_limiter
import app.core.security as security_module
from app.main import app

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


@pytest.fixture(scope="module")
def ec_keypair():
    """Generate in-memory EC keypair for ES256 signing (matching Supabase)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="module")
def untrusted_ec_keypair():
    """Generate a secondary EC keypair to test signature mismatch."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


def generate_test_jwt(
    private_key,
    user_id: str,
    email: str = "fan@cricketgpt.com",
    role: str = "authenticated",
    full_name: str = "MS Dhoni",
    provider: str = "google",
    exp_offset: int = 3600,
    iss: str = TEST_ISSUER,
    aud: str = TEST_AUDIENCE,
) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "user_metadata": {"full_name": full_name},
        "app_metadata": {"provider": provider},
        "exp": now + exp_offset,
        "iat": now,
        "iss": iss,
        "aud": aud,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": "test-kid"})


@pytest.fixture
def auth_client(ec_keypair, monkeypatch):
    """TestClient wired with in-memory public key for authenticating requests."""
    reset_rate_limiter()
    _, public_key = ec_keypair

    monkeypatch.setenv("SUPABASE_JWT_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", TEST_AUDIENCE)
    monkeypatch.setenv("SUPABASE_JWT_ALGORITHMS", "ES256")

    original_verify = security_module.verify_supabase_token

    def mock_verify(token: str):
        return original_verify(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )

    monkeypatch.setattr(security_module, "verify_supabase_token", mock_verify)

    with TestClient(app) as client:
        yield client
    reset_rate_limiter()


# ---------------------------------------------------------------------------
# 1. Chat without token returns 401
# ---------------------------------------------------------------------------

def test_chat_without_token_returns_401(auth_client: TestClient):
    """Verify that calling POST /api/chat with no credentials returns HTTP 401."""
    response = auth_client.post("/api/chat", json={"question": "Who won IPL 2024?"})
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]
    assert "Bearer" in response.headers.get("www-authenticate", "")


# ---------------------------------------------------------------------------
# 2. Chat with invalid token returns 401
# ---------------------------------------------------------------------------

def test_chat_with_non_bearer_scheme_returns_401(auth_client: TestClient):
    """Verify that passing an invalid auth scheme (e.g. Basic) returns HTTP 401."""
    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won IPL 2024?"},
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401
    assert "Expected 'Bearer'" in response.json()["detail"]


def test_chat_with_malformed_token_returns_401(auth_client: TestClient):
    """Verify that passing a malformed string returns HTTP 401."""
    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won IPL 2024?"},
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401
    detail = response.json()["detail"].lower()
    assert "malformed" in detail or "invalid" in detail


def test_chat_with_expired_token_returns_401(auth_client: TestClient, ec_keypair):
    """Verify that an expired token returns HTTP 401."""
    private_key, _ = ec_keypair
    expired_token = generate_test_jwt(private_key, user_id=str(uuid.uuid4()), exp_offset=-100)

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won IPL 2024?"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_chat_with_untrusted_signature_returns_401(auth_client: TestClient, untrusted_ec_keypair):
    """Verify that a token signed by an unknown key returns HTTP 401."""
    untrusted_private, _ = untrusted_ec_keypair
    tampered_token = generate_test_jwt(untrusted_private, user_id=str(uuid.uuid4()))

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won IPL 2024?"},
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Chat with valid token reaches the existing handler
# ---------------------------------------------------------------------------

@patch("app.api.routes.chat.route_question")
def test_chat_with_valid_token_reaches_handler(mock_route, auth_client: TestClient, ec_keypair):
    """Verify that a valid token is accepted and reaches the question answering router."""
    mock_route.return_value = "Kolkata Knight Riders won IPL 2024 by 8 wickets."
    private_key, _ = ec_keypair
    user_id = str(uuid.uuid4())
    valid_token = generate_test_jwt(private_key, user_id=user_id, email="rohit@mi.com")

    response = auth_client.post(
        "/api/chat",
        json={"question": "Who won IPL 2024?"},
        headers={"Authorization": f"Bearer {valid_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Who won IPL 2024?"
    assert data["answer"] == "Kolkata Knight Riders won IPL 2024 by 8 wickets."
    mock_route.assert_called_once_with("Who won IPL 2024?")

    # Verify rate limit headers were applied
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


# ---------------------------------------------------------------------------
# 4. Public cricket endpoints remain accessible without auth
# ---------------------------------------------------------------------------

@patch("app.api.routes.teams.get_teams_overall_statistics", return_value=[])
@patch("app.api.routes.leaderboards.get_batting_leaderboard", return_value=[])
@patch("app.api.routes.players.get_batting_leaderboard", return_value=[])
def test_public_cricket_endpoints_remain_accessible(
    mock_player_lead, mock_lead, mock_teams, auth_client: TestClient
):
    """Verify that public stats endpoints do not require authentication."""
    # Service health
    health_res = auth_client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # App info
    info_res = auth_client.get("/api/info")
    assert info_res.status_code == 200

    # Teams
    teams_res = auth_client.get("/api/teams")
    assert teams_res.status_code == 200

    # Leaderboards
    lead_res = auth_client.get("/api/leaderboards/batting?limit=5")
    assert lead_res.status_code == 200

    # Player stats
    player_res = auth_client.get("/api/players/leaderboard/batting?limit=5")
    assert player_res.status_code == 200


# ---------------------------------------------------------------------------
# 5. Ingestion API-key protection still works
# ---------------------------------------------------------------------------

def test_ingestion_api_key_protection_still_works(auth_client: TestClient, monkeypatch):
    """Verify that /api/rag/ingest continues to require INGESTION_API_KEY."""
    monkeypatch.setenv("INGESTION_API_KEY", "super-secret-ingestion-token")

    payload = {
        "source_key": "ipl_2024_final",
        "title": "IPL 2024 Final Report",
        "text": "Detailed match report of the final between KKR and SRH...",
        "doc_type": "match_report",
    }

    # 1. Missing credentials -> 401
    res_no_auth = auth_client.post("/api/rag/ingest", json=payload)
    assert res_no_auth.status_code == 401
    assert "Missing ingestion authentication credentials" in res_no_auth.json()["detail"]

    # 2. Wrong credentials -> 403
    res_wrong_auth = auth_client.post(
        "/api/rag/ingest",
        json=payload,
        headers={"X-API-Key": "wrong-token"},
    )
    assert res_wrong_auth.status_code == 403
    assert "Invalid ingestion API key" in res_wrong_auth.json()["detail"]

    # 3. Valid credentials via X-API-Key reaches ingestion handler
    with patch("app.api.routes.rag.ingest_document") as mock_ingest:
        mock_ingest.return_value = {
            "source_key": "ipl_2024_final",
            "doc_id": 101,
            "status": "ingested",
            "chunk_count": 3,
        }
        res_valid = auth_client.post(
            "/api/rag/ingest",
            json=payload,
            headers={"X-API-Key": "super-secret-ingestion-token"},
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["doc_id"] == 101
