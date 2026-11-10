"""
CricketGPT — Database Connection and Health Tests

These tests use mocking so they run instantly in-memory without requiring
a live internet connection or real Supabase credentials.
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.database.connection import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    check_database_connection,
    create_connection,
    get_database_url,
    get_sanitized_connection_details,
    get_sanitized_host,
    sanitize_connection_error_message,
)
from app.main import app


@pytest.fixture
def client():
    """Create a test client that talks directly to the FastAPI app."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Configuration & Sanitization Tests
# ---------------------------------------------------------------------------

def test_get_database_url_raises_when_missing():
    """get_database_url must raise DatabaseConfigurationError when not set."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(DatabaseConfigurationError):
            get_database_url()


def test_get_database_url_returns_clean_value():
    """get_database_url returns stripped string when set."""
    fake_url = "postgresql://user:pass@db.example.com:5432/postgres  "
    with patch.dict("os.environ", {"DATABASE_URL": fake_url}):
        assert get_database_url() == fake_url.strip()


def test_get_sanitized_host_extracts_only_hostname():
    """get_sanitized_host must never leak username or password."""
    url_with_secret = "postgresql://myuser:supersecretpass@db.supabase.co:5432/postgres"
    host = get_sanitized_host(url_with_secret)
    assert host == "db.supabase.co"
    assert "supersecretpass" not in host
    assert "myuser" not in host


def test_sanitize_connection_error_message_redacts_credentials_and_dsn():
    url = "postgresql://postgres.projref123:s3cr3t%40pass@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"
    raw = (
        f'connection failed to "{url}": FATAL: password authentication failed '
        'for user "postgres.projref123" password=s3cr3t@pass user=postgres.projref123'
    )
    cleaned = sanitize_connection_error_message(raw, db_url=url)
    assert "s3cr3t" not in cleaned
    assert "projref123" not in cleaned
    assert "postgres.projref123" not in cleaned
    assert url not in cleaned
    assert "[REDACTED]" in cleaned


def test_get_sanitized_connection_details_checks_pooler_format_without_leaking_secrets():
    good_url = "postgresql://postgres.projref123:secret@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    details = get_sanitized_connection_details(good_url)
    assert details["host"] == "aws-0-ap-northeast-1.pooler.supabase.com"
    assert details["port"] == 5432
    assert details["effective_sslmode"] == "require"
    assert details["connect_timeout"] == 10
    assert details["is_supabase_pooler"] is True
    assert details["pooler_username_has_project_ref"] is True
    assert "secret" not in str(details)
    assert "projref123" not in str(details)

    bad_user_url = "postgresql://postgres:secret@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"
    bad_details = get_sanitized_connection_details(bad_user_url)
    assert bad_details["is_supabase_pooler"] is True
    assert bad_details["pooler_username_has_project_ref"] is False


def test_create_connection_logs_sanitized_diagnostics_without_credentials(caplog):
    import psycopg

    fake_url = "postgresql://postgres.projref123:supersecret@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

    class FakeOperationalError(psycopg.OperationalError):
        sqlstate = "XX000"

    raw_err = FakeOperationalError(
        'connection failed: FATAL: Tenant or user not found for user "postgres.projref123" '
        f"dsn={fake_url}"
    )

    with patch.dict("os.environ", {"DATABASE_URL": fake_url}):
        with patch("app.database.connection.psycopg.connect", side_effect=raw_err):
            with caplog.at_level("ERROR", logger="app.database.connection"):
                with pytest.raises(DatabaseConnectionError) as exc_info:
                    create_connection()

    raised_msg = str(exc_info.value)
    logged_msg = caplog.text

    for text in (raised_msg, logged_msg):
        assert "aws-0-ap-northeast-1.pooler.supabase.com" in text
        assert "5432" in text
        assert "sslmode=require" in text
        assert "FakeOperationalError" in text
        assert "sqlstate=XX000" in text
        assert "supersecret" not in text
        assert "projref123" not in text
        assert fake_url not in text


# ---------------------------------------------------------------------------
# Database Connectivity Unit Tests (Mocked)
# ---------------------------------------------------------------------------

def test_check_database_connection_success():
    """check_database_connection returns expected dict when queries succeed."""
    mock_cursor = MagicMock()
    # First query (SELECT 1;) returns (1,), second query (SELECT version();) returns PostgreSQL info
    mock_cursor.fetchone.side_effect = [(1,), ("PostgreSQL 15.1 on x86_64",)]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("app.database.connection.create_connection", return_value=mock_conn):
        result = check_database_connection()
        assert result["status"] == "connected"
        assert result["database"] == "Supabase PostgreSQL"


def test_check_database_connection_fails_on_connection_error():
    """check_database_connection raises DatabaseConnectionError safely on connection failure."""
    with patch(
        "app.database.connection.create_connection",
        side_effect=DatabaseConnectionError("Failed to connect to database host 'db.example.com'"),
    ):
        with pytest.raises(DatabaseConnectionError):
            check_database_connection()


# ---------------------------------------------------------------------------
# API Endpoint Tests (/health/database)
# ---------------------------------------------------------------------------

def test_database_health_endpoint_success(client: TestClient):
    """GET /health/database returns 200 OK when database is reachable."""
    with patch(
        "app.main.check_database_connection",
        return_value={"status": "connected", "database": "Supabase PostgreSQL"},
    ):
        response = client.get("/health/database")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["database"] == "Supabase PostgreSQL"


def test_database_health_endpoint_service_unavailable_on_failure(client: TestClient):
    """GET /health/database returns 503 Service Unavailable when database fails."""
    with patch(
        "app.main.check_database_connection",
        side_effect=DatabaseConnectionError("Host unreachable"),
    ):
        response = client.get("/health/database")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["message"] == "Database connection failed"
        # Ensure no technical stack traces or secrets leak in response body
        assert "password" not in str(data)
        assert "Host unreachable" not in str(data)


def test_service_health_remains_independent(client: TestClient):
    """GET /health must remain 200 healthy even if database check fails."""
    with patch(
        "app.main.check_database_connection",
        side_effect=DatabaseConnectionError("Database down"),
    ):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

