"""
CricketGPT — Database Connection Module

This module manages connections to Supabase PostgreSQL using psycopg 3.

Key concepts:
- Environment Variables: DATABASE_URL is loaded from .env without hardcoding secrets.
- Connection Management: Connections are opened, used, and properly closed.
- Context Manager: The `get_db_connection()` context manager ensures connections
  are always closed, even if errors occur during execution.
- Security: Passwords and sensitive connection strings are never exposed in logs
  or exception messages.
- SSL: Supabase requires encrypted connections (sslmode=require).
"""

import os
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg

# Load environment variables from .env file (if present)
load_dotenv()


class DatabaseConfigurationError(Exception):
    """Raised when database configuration (like DATABASE_URL) is missing or invalid."""
    pass


class DatabaseConnectionError(Exception):
    """Raised when connecting to the database fails, with secrets sanitized."""
    pass


def get_database_url() -> str:
    """
    Retrieve and validate the DATABASE_URL environment variable.

    Returns:
        The validated PostgreSQL connection string.

    Raises:
        DatabaseConfigurationError: If DATABASE_URL is not set or empty.
    """
    url = os.getenv("DATABASE_URL")
    if not url or url.strip() == "":
        raise DatabaseConfigurationError(
            "DATABASE_URL environment variable is not set. "
            "Please configure it in your .env file."
        )
    return url.strip()


def get_sanitized_host(url: str) -> str:
    """
    Extract only the host name from the connection URL for safe logging/errors.
    Never returns passwords or credentials.
    """
    try:
        parsed = urlparse(url)
        return parsed.hostname or "unknown-host"
    except Exception:
        return "unknown-host"


def create_connection() -> psycopg.Connection:
    """
    Establish a single new connection to Supabase PostgreSQL.

    Supabase requires an encrypted SSL connection. If 'sslmode' is not
    already present in the connection string, sslmode='require' is enforced.

    Returns:
        An open psycopg.Connection instance.

    Raises:
        DatabaseConfigurationError: If DATABASE_URL is missing.
        DatabaseConnectionError: If the connection attempt fails (sanitized).
    """
    db_url = get_database_url()
    host = get_sanitized_host(db_url)

    try:
        # Enforce SSL requirement for Supabase cloud PostgreSQL
        conn = psycopg.connect(db_url, sslmode="require", connect_timeout=10)
        return conn
    except psycopg.OperationalError as exc:
        # OperationalError includes network failures, wrong password, host unreachable
        raise DatabaseConnectionError(
            f"Failed to connect to database host '{host}'. Please verify your credentials and network."
        ) from None
    except psycopg.Error as exc:
        raise DatabaseConnectionError(
            f"Database error while connecting to '{host}'."
        ) from None
    except Exception as exc:
        raise DatabaseConnectionError(
            f"Unexpected error while connecting to database host '{host}'."
        ) from None


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Context manager that provides a database connection and ensures it is closed.

    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                result = cur.fetchone()

    Guarantees:
        `conn.close()` is always called in the `finally` block, preventing
        idle connection leaks on Supabase.
    """
    conn = create_connection()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def check_database_connection() -> dict:
    """
    Test connectivity to Supabase PostgreSQL by executing a lightweight query.

    Queries:
        1. 'SELECT 1;' — Verifies the database engine is alive and accepting queries.
        2. 'SELECT version();' — Confirms PostgreSQL engine metadata.

    Returns:
        dict: {"status": "connected", "database": "Supabase PostgreSQL"}

    Raises:
        DatabaseConfigurationError: If DATABASE_URL is not set.
        DatabaseConnectionError: If connection or execution fails.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Verification query: SELECT 1
            cur.execute("SELECT 1;")
            result = cur.fetchone()

            if result is None or result[0] != 1:
                raise DatabaseConnectionError(
                    "Database verification query (SELECT 1) returned unexpected result."
                )

            # 2. Metadata query: check that we are talking to PostgreSQL
            cur.execute("SELECT version();")
            version_info = cur.fetchone()

            if not version_info or "PostgreSQL" not in version_info[0]:
                raise DatabaseConnectionError(
                    "Connected database is not a recognized PostgreSQL instance."
                )

    return {
        "status": "connected",
        "database": "Supabase PostgreSQL",
    }

