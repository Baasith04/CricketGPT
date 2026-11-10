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

import logging
import os
import re
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv
import psycopg

# Load environment variables from .env file (if present)
load_dotenv()

logger = logging.getLogger(__name__)


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


def get_sanitized_connection_details(url: str) -> Dict[str, Any]:
    """
    Extract non-secret connection attributes (host, port, SSL mode, pooler format flags)
    without ever returning username, password, or the raw connection string.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "unknown-host"
        port = parsed.port or 5432
        query = parse_qs(parsed.query)
        sslmode_values = query.get("sslmode")
        sslmode_in_url = sslmode_values[0] if sslmode_values else None
        username = parsed.username
        password = parsed.password
        has_dbname = bool(parsed.path and parsed.path.strip("/"))
        is_pooler = host.endswith(".pooler.supabase.com")
        pooler_user_ok = bool(
            username
            and "." in username
            and not username.startswith(".")
            and not username.endswith(".")
        )
        return {
            "scheme": parsed.scheme or "",
            "host": host,
            "port": port,
            "sslmode_in_url": sslmode_in_url,
            "effective_sslmode": "require",
            "connect_timeout": 10,
            "is_supabase_pooler": is_pooler,
            "pooler_username_has_project_ref": pooler_user_ok,
            "has_username": bool(username),
            "has_password": bool(password),
            "has_dbname": has_dbname,
        }
    except Exception:
        return {
            "scheme": "",
            "host": "unknown-host",
            "port": 5432,
            "sslmode_in_url": None,
            "effective_sslmode": "require",
            "connect_timeout": 10,
            "is_supabase_pooler": False,
            "pooler_username_has_project_ref": False,
            "has_username": False,
            "has_password": False,
            "has_dbname": False,
        }


def sanitize_connection_error_message(message: str, db_url: Optional[str] = None) -> str:
    """
    Remove credentials, usernames, passwords, and connection strings from a raw
    database exception message before logging or raising.
    """
    sanitized = str(message or "")
    if db_url:
        secrets_to_mask = [db_url, unquote(db_url)]
        try:
            parsed = urlparse(db_url)
            for raw_secret in (parsed.password, parsed.username):
                if raw_secret:
                    secrets_to_mask.append(raw_secret)
                    secrets_to_mask.append(unquote(raw_secret))
        except Exception:
            pass
        for secret in sorted({s for s in secrets_to_mask if s}, key=len, reverse=True):
            sanitized = sanitized.replace(secret, "[REDACTED]")

    sanitized = re.sub(r"postgres(?:ql)?://[^\s@]+@", "postgresql://[REDACTED]@", sanitized)
    sanitized = re.sub(
        r"(?i)(password\s*=\s*)(?:'[^']*'|\"[^\"]*\"|\S+)",
        r"\1[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)(user\s*=\s*)(?:'[^']*'|\"[^\"]*\"|\S+)",
        r"\1[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r'(?i)(for user\s+)(?:"[^"]*"|\'[^\']*\'|\S+)',
        r'\1"[REDACTED]"',
        sanitized,
    )
    return sanitized.strip() or "No error details provided."


def _log_and_raise_connection_error(
    exc: Exception,
    db_url: str,
    details: Dict[str, Any],
    prefix: str,
) -> None:
    """Log sanitized diagnostic details for a connection failure and raise DatabaseConnectionError."""
    exc_class = f"{type(exc).__module__}.{type(exc).__name__}"
    sqlstate = getattr(exc, "sqlstate", None)
    sanitized_msg = sanitize_connection_error_message(str(exc), db_url=db_url)
    logger.error(
        "%s: host=%s port=%s sslmode=%s connect_timeout=%s exception_class=%s sqlstate=%s message=%s",
        prefix,
        details["host"],
        details["port"],
        details["effective_sslmode"],
        details["connect_timeout"],
        exc_class,
        sqlstate or "N/A",
        sanitized_msg,
    )
    raise DatabaseConnectionError(
        f"{prefix} '{details['host']}' (port={details['port']}, "
        f"sslmode={details['effective_sslmode']}, {exc_class}, "
        f"sqlstate={sqlstate or 'N/A'}): {sanitized_msg}"
    ) from None


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
    details = get_sanitized_connection_details(db_url)

    try:
        # Enforce SSL requirement for Supabase cloud PostgreSQL
        conn = psycopg.connect(
            db_url,
            sslmode=details["effective_sslmode"],
            connect_timeout=details["connect_timeout"],
        )
        return conn
    except psycopg.OperationalError as exc:
        _log_and_raise_connection_error(
            exc, db_url, details, "Failed to connect to database host"
        )
    except psycopg.Error as exc:
        _log_and_raise_connection_error(
            exc, db_url, details, "Database error while connecting to"
        )
    except Exception as exc:
        _log_and_raise_connection_error(
            exc, db_url, details, "Unexpected error while connecting to database host"
        )


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

