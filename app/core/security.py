"""
CricketGPT — Supabase JWT Authentication Foundation

Provides cryptographic JWT verification for Supabase Auth, extracting
authenticated user identity into type-safe Pydantic models.

Features:
- Prefers asymmetric JWKS verification (ES256/RS256) matching live Supabase config.
- Caches JWKS keys with thread-safety and automatic key rotation support.
- Enforces strict allowed algorithms (never trusts unverified header alg).
- Validates signature, expiration, issuer, audience, and not-before claims.
- Extracts sub (UUID), email, role, full_name, and provider.
- Fail-closed error handling returning HTTP 401 on missing/invalid/expired tokens.
"""

import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient, PyJWKClientError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Reusable HTTPBearer security scheme (auto_error=False to allow clean custom 401s and optional auth)
oauth2_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Pydantic Identity Models
# ---------------------------------------------------------------------------

class AuthenticatedUser(BaseModel):
    """Represents a verified Supabase authenticated user."""

    id: UUID = Field(..., description="Canonical user UUID (sub)")
    email: Optional[str] = Field(default=None, description="User email address")
    role: str = Field(default="authenticated", description="Supabase auth role")
    full_name: Optional[str] = Field(
        default=None,
        description="Display name from user_metadata.full_name",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Authentication provider from app_metadata.provider",
    )
    raw_claims: Dict[str, Any] = Field(
        default_factory=dict,
        repr=False,
        description="Complete raw validated JWT claims dictionary",
    )


# ---------------------------------------------------------------------------
# Configuration Helpers
# ---------------------------------------------------------------------------

def get_supabase_url() -> str:
    """
    Return the base Supabase URL from SUPABASE_URL, or deduce project ref from DATABASE_URL.
    Trailing slashes are stripped.
    """
    explicit = os.getenv("SUPABASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    # Fallback: parse project reference from DATABASE_URL if available
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        try:
            parsed = urlparse(db_url)
            # Username format: postgres.<project-ref>
            username = parsed.username or ""
            if username.startswith("postgres."):
                project_ref = username.split(".", 1)[1]
                return f"https://{project_ref}.supabase.co"
        except Exception:
            pass

    return ""


def get_supabase_jwt_issuer() -> str:
    """Return the expected JWT issuer claim (iss)."""
    explicit = os.getenv("SUPABASE_JWT_ISSUER", "").strip()
    if explicit:
        return explicit.rstrip("/")

    base_url = get_supabase_url()
    if base_url:
        return f"{base_url}/auth/v1"

    return ""


def get_supabase_jwt_audience() -> str:
    """Return the expected JWT audience claim (aud). Default: 'authenticated'."""
    return os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip() or "authenticated"


def get_supabase_jwks_url() -> str:
    """Return the JWKS endpoint URL."""
    explicit = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if explicit:
        return explicit

    base_url = get_supabase_url()
    if base_url:
        return f"{base_url}/auth/v1/.well-known/jwks.json"

    return ""


def get_supabase_jwt_secret() -> Optional[str]:
    """Return optional symmetric JWT secret for HS256 fallback if configured."""
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    return secret if secret else None


def get_allowed_algorithms() -> List[str]:
    """
    Return allowed JWT signing algorithms.
    Defaults to asymmetric algorithms ('ES256', 'RS256').
    If SUPABASE_JWT_SECRET is explicitly configured, 'HS256' is also permitted.
    """
    explicit = os.getenv("SUPABASE_JWT_ALGORITHMS", "").strip()
    if explicit:
        return [alg.strip() for alg in explicit.split(",") if alg.strip()]

    algorithms = ["ES256", "RS256"]
    if get_supabase_jwt_secret():
        algorithms.append("HS256")
    return algorithms


# ---------------------------------------------------------------------------
# JWKS Client Management & Caching
# ---------------------------------------------------------------------------

_jwks_lock = threading.Lock()
_cached_jwks_url: Optional[str] = None
_cached_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client(jwks_url: Optional[str] = None) -> PyJWKClient:
    """
    Thread-safe getter for the cached PyJWKClient instance.
    Supports key rotation and automatic cache refresh via PyJWKClient.
    """
    global _cached_jwks_url, _cached_jwks_client

    target_url = jwks_url or get_supabase_jwks_url()
    if not target_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase JWKS URL is not configured.",
        )

    with _jwks_lock:
        if _cached_jwks_client is not None and _cached_jwks_url == target_url:
            return _cached_jwks_client

        # PyJWKClient automatically caches keys, invalidating on unknown kid (key rotation)
        _cached_jwks_client = PyJWKClient(
            target_url,
            cache_jwk_set=True,
            lifespan=float(os.getenv("SUPABASE_JWKS_CACHE_SECONDS", "300")),
            timeout=float(os.getenv("SUPABASE_JWKS_TIMEOUT_SECONDS", "10")),
            cooldown_duration=30.0,
        )
        _cached_jwks_url = target_url
        return _cached_jwks_client


def reset_jwks_client() -> None:
    """Clear cached JWKS client (primarily used for unit testing)."""
    global _cached_jwks_url, _cached_jwks_client
    with _jwks_lock:
        _cached_jwks_url = None
        _cached_jwks_client = None


# ---------------------------------------------------------------------------
# JWT Token Verification Core
# ---------------------------------------------------------------------------

def verify_supabase_token(
    token: str,
    jwks_client: Optional[PyJWKClient] = None,
    custom_key: Optional[Any] = None,
    expected_issuer: Optional[str] = None,
    expected_audience: Optional[str] = None,
    allowed_algorithms: Optional[List[str]] = None,
) -> AuthenticatedUser:
    """
    Cryptographically verify a Supabase access token and extract user identity.

    Args:
        token: Raw JWT string.
        jwks_client: Optional injected PyJWKClient (defaults to cached client).
        custom_key: Optional key for testing or static secret verification.
        expected_issuer: Optional expected issuer override.
        expected_audience: Optional expected audience override.
        allowed_algorithms: Optional algorithm whitelist override.

    Returns:
        AuthenticatedUser instance with validated claims.

    Raises:
        HTTPException(401): On any signature, expiration, claim, or network validation failure.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token.strip()
    configured_algorithms = allowed_algorithms or get_allowed_algorithms()

    # 1. Inspect unverified header strictly to validate algorithm against whitelist
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token header.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc

    alg = header.get("alg")
    if not alg or alg not in configured_algorithms:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token signing algorithm '{alg}' is not permitted.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    # 2. Resolve signing key based on algorithm
    if custom_key is not None:
        signing_key_obj = custom_key
    elif alg == "HS256":
        secret = get_supabase_jwt_secret()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Symmetric token verification is not configured.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        signing_key_obj = secret
    else:
        # Asymmetric verification via JWKS
        client = jwks_client or get_jwks_client()
        try:
            key_match = client.get_signing_key_from_jwt(token)
            signing_key_obj = key_match.key
        except (PyJWKClientError, Exception) as exc:
            logger.warning(
                "Failed to retrieve JWKS signing key for token (%s: %s).",
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify token signature: public key resolution failed.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            ) from exc

    # 3. Cryptographically verify signature, claims, expiration, and issuer
    issuer = expected_issuer if expected_issuer is not None else get_supabase_jwt_issuer()
    audience = expected_audience if expected_audience is not None else get_supabase_jwt_audience()
    leeway = float(os.getenv("SUPABASE_JWT_LEEWAY_SECONDS", "10"))

    decode_options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iat": True,
        "verify_aud": bool(audience),
        "verify_iss": bool(issuer),
        "require": ["exp", "sub"],
    }

    try:
        claims = jwt.decode(
            token,
            signing_key_obj,
            algorithms=[alg],
            audience=audience or None,
            issuer=issuer or None,
            options=decode_options,
            leeway=leeway,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"token expired\""},
        ) from exc
    except jwt.ImmatureSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is not yet valid (nbf claim).",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer does not match the configured Supabase issuer.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience does not match the expected audience.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc
    except jwt.InvalidSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature verification failed.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc
    except jwt.MissingRequiredClaimError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing required claim: {exc}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc

    # 4. Extract and validate user identity
    sub_raw = claims.get("sub")
    if not sub_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing user identifier (sub).",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    try:
        user_uuid = UUID(str(sub_raw))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token user identifier (sub) is not a valid UUID.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc

    user_meta = claims.get("user_metadata") or {}
    app_meta = claims.get("app_metadata") or {}

    return AuthenticatedUser(
        id=user_uuid,
        email=claims.get("email"),
        role=claims.get("role", "authenticated"),
        full_name=user_meta.get("full_name"),
        provider=app_meta.get("provider"),
        raw_claims=claims,
    )


# ---------------------------------------------------------------------------
# FastAPI Route Dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
) -> AuthenticatedUser:
    """
    FastAPI dependency requiring a valid Supabase Bearer token.
    Returns the verified AuthenticatedUser or raises HTTP 401.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Expected 'Bearer'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = verify_supabase_token(credentials.credentials)
    request.state.user = user
    return user


def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency for optional authentication.
    - If no Authorization header is provided: returns None.
    - If an Authorization header is provided: cryptographically validates it and
      returns AuthenticatedUser, or raises HTTP 401 if invalid.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Expected 'Bearer'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = verify_supabase_token(credentials.credentials)
    request.state.user = user
    return user
