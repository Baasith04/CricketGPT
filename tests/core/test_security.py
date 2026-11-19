"""
Tests for CricketGPT Supabase JWT Authentication Foundation

Verifies:
1. Valid JWT verification & identity extraction (UUID, email, role, full_name, provider).
2. Missing token handling (HTTP 401).
3. Invalid signature rejection (HTTP 401).
4. Expired JWT rejection (HTTP 401).
5. Wrong issuer rejection (HTTP 401).
6. Wrong audience rejection (HTTP 401).
7. Missing subject (sub) claim rejection (HTTP 401).
8. Invalid subject UUID format rejection (HTTP 401).
9. Optional authentication with no token (returns None).
10. Optional authentication with valid token (returns AuthenticatedUser).
11. Disallowed algorithm rejection (e.g. 'none' or unconfigured alg).
12. Immature token rejection (nbf claim).
13. FastAPI route integration via TestClient.
"""

import time
import uuid
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
import jwt
import pytest

from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    get_optional_user,
    verify_supabase_token,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Key Generation
# ---------------------------------------------------------------------------

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


@pytest.fixture(scope="module")
def ec_keypair():
    """Generate in-memory EC keypair for ES256 signing (matching Supabase)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="module")
def another_ec_keypair():
    """Generate a second EC keypair to test invalid signatures."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


def create_token(
    private_key,
    sub: Optional[str] = None,
    email: str = "virat@rcb.com",
    role: str = "authenticated",
    full_name: str = "Virat Kohli",
    provider: str = "google",
    iss: str = TEST_ISSUER,
    aud: str = TEST_AUDIENCE,
    exp_offset: int = 3600,
    nbf_offset: Optional[int] = None,
    alg: str = "ES256",
    kid: str = "test-key-id",
    omit_sub: bool = False,
) -> str:
    """Helper to generate JWT tokens with configurable claims."""
    now = int(time.time())
    payload = {
        "exp": now + exp_offset,
        "iat": now,
        "iss": iss,
        "aud": aud,
        "email": email,
        "role": role,
        "user_metadata": {"full_name": full_name},
        "app_metadata": {"provider": provider},
    }

    if not omit_sub:
        payload["sub"] = sub or str(uuid.uuid4())

    if nbf_offset is not None:
        payload["nbf"] = now + nbf_offset

    headers = {"kid": kid, "typ": "JWT"}
    return jwt.encode(payload, private_key, algorithm=alg, headers=headers)


# ---------------------------------------------------------------------------
# Core Verification Tests
# ---------------------------------------------------------------------------

def test_valid_jwt_verification(ec_keypair):
    """Test that a valid JWT succeeds and extracts all user identity fields."""
    private_key, public_key = ec_keypair
    user_id = str(uuid.uuid4())

    token = create_token(
        private_key,
        sub=user_id,
        email="virat@rcb.com",
        full_name="Virat Kohli",
        provider="google",
    )

    user = verify_supabase_token(
        token,
        custom_key=public_key,
        expected_issuer=TEST_ISSUER,
        expected_audience=TEST_AUDIENCE,
        allowed_algorithms=["ES256"],
    )

    assert isinstance(user, AuthenticatedUser)
    assert user.id == uuid.UUID(user_id)
    assert user.email == "virat@rcb.com"
    assert user.role == "authenticated"
    assert user.full_name == "Virat Kohli"
    assert user.provider == "google"
    assert user.raw_claims["iss"] == TEST_ISSUER


def test_missing_token():
    """Test that verifying an empty or whitespace token raises HTTP 401."""
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token("")
    assert exc_info.value.status_code == 401
    assert "Missing authentication token" in exc_info.value.detail


def test_invalid_signature(ec_keypair, another_ec_keypair):
    """Test that a token signed with an untrusted key raises HTTP 401."""
    private_key, _ = ec_keypair
    _, untrusted_public_key = another_ec_keypair

    token = create_token(private_key)

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=untrusted_public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "signature verification failed" in exc_info.value.detail.lower()


def test_expired_jwt(ec_keypair):
    """Test that an expired token raises HTTP 401."""
    private_key, public_key = ec_keypair

    token = create_token(private_key, exp_offset=-60)  # expired 60 seconds ago

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_wrong_issuer(ec_keypair):
    """Test that a token with an unexpected issuer raises HTTP 401."""
    private_key, public_key = ec_keypair

    token = create_token(private_key, iss="https://rogue-supabase.co/auth/v1")

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail.lower()


def test_wrong_audience(ec_keypair):
    """Test that a token with an unexpected audience raises HTTP 401."""
    private_key, public_key = ec_keypair

    token = create_token(private_key, aud="unauthorized-service")

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail.lower()


def test_missing_subject(ec_keypair):
    """Test that a token missing the sub claim raises HTTP 401."""
    private_key, public_key = ec_keypair

    token = create_token(private_key, omit_sub=True)

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "sub" in exc_info.value.detail.lower()


def test_invalid_subject_uuid(ec_keypair):
    """Test that a token whose sub claim is not a valid UUID raises HTTP 401."""
    private_key, public_key = ec_keypair

    token = create_token(private_key, sub="not-a-valid-uuid")

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "uuid" in exc_info.value.detail.lower()


def test_disallowed_algorithm(ec_keypair):
    """Test that a token signed with an algorithm not in the whitelist is rejected."""
    private_key, public_key = ec_keypair

    # Create token with ES256, but only allow RS256
    token = create_token(private_key, alg="ES256")

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["RS256"],
        )
    assert exc_info.value.status_code == 401
    assert "not permitted" in exc_info.value.detail.lower()


def test_immature_token_nbf(ec_keypair):
    """Test that a token with nbf in the future raises HTTP 401."""
    private_key, public_key = ec_keypair

    token = create_token(private_key, nbf_offset=600)  # valid only in 10 minutes

    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_token(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )
    assert exc_info.value.status_code == 401
    assert "nbf" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# FastAPI Dependency & Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app(ec_keypair, monkeypatch):
    """Create a minimal FastAPI test app demonstrating get_current_user and get_optional_user."""
    _, public_key = ec_keypair

    # Configure environment for test app
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", TEST_AUDIENCE)
    monkeypatch.setenv("SUPABASE_JWT_ALGORITHMS", "ES256")

    # Patch verify_supabase_token so test app uses in-memory public key
    import app.core.security as sec_module
    original_verify = sec_module.verify_supabase_token

    def mock_verify(token: str):
        return original_verify(
            token,
            custom_key=public_key,
            expected_issuer=TEST_ISSUER,
            expected_audience=TEST_AUDIENCE,
            allowed_algorithms=["ES256"],
        )

    monkeypatch.setattr(sec_module, "verify_supabase_token", mock_verify)

    app = FastAPI()

    @app.get("/protected")
    def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
        return {"user_id": str(user.id), "email": user.email, "role": user.role}

    @app.get("/optional")
    def optional_route(user: Optional[AuthenticatedUser] = Depends(get_optional_user)):
        if user is None:
            return {"authenticated": False}
        return {"authenticated": True, "user_id": str(user.id)}

    return app


def test_dependency_missing_token(test_app):
    """Test that accessing a protected route without a token returns HTTP 401."""
    client = TestClient(test_app)
    response = client.get("/protected")
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]
    assert "Bearer" in response.headers.get("www-authenticate", "")


def test_dependency_invalid_scheme(test_app):
    """Test that passing a non-Bearer scheme returns HTTP 401."""
    client = TestClient(test_app)
    response = client.get("/protected", headers={"Authorization": "Basic 12345"})
    assert response.status_code == 401
    assert "Expected 'Bearer'" in response.json()["detail"]


def test_dependency_valid_token(test_app, ec_keypair):
    """Test that accessing a protected route with a valid Bearer token succeeds."""
    private_key, _ = ec_keypair
    user_id = str(uuid.uuid4())
    token = create_token(private_key, sub=user_id, email="rohit@mi.com")

    client = TestClient(test_app)
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["email"] == "rohit@mi.com"
    assert data["role"] == "authenticated"


def test_optional_auth_without_token(test_app):
    """Test that optional authentication without a token returns None (anonymous)."""
    client = TestClient(test_app)
    response = client.get("/optional")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_optional_auth_with_valid_token(test_app, ec_keypair):
    """Test that optional authentication with a valid token identifies the user."""
    private_key, _ = ec_keypair
    user_id = str(uuid.uuid4())
    token = create_token(private_key, sub=user_id)

    client = TestClient(test_app)
    response = client.get("/optional", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user_id"] == user_id


def test_optional_auth_with_invalid_token(test_app, ec_keypair, another_ec_keypair):
    """Test that optional auth with an explicitly provided BAD token raises HTTP 401 rather than silently ignoring."""
    _, untrusted_public = another_ec_keypair
    private_key, _ = ec_keypair

    # Create token with untrusted key
    another_private, _ = another_ec_keypair
    token = create_token(another_private)

    client = TestClient(test_app)
    response = client.get("/optional", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"].lower()
