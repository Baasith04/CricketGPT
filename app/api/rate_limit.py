"""
CricketGPT — Configurable, Multi-Worker & Multi-Instance Rate Limiter

Supports:
- Redis (`redis://` / `rediss://` via `RATE_LIMIT_STORAGE_URI` or `REDIS_URL`) for
  multi-instance horizontal scaling.
- Shared SQLite WAL (`sqlite:///...` or default temp file) for multi-worker Uvicorn
  deployments on a single host without altering Supabase schema.
- In-memory backend (`memory://`) for isolated testing.
"""

import ipaddress
import logging
import os
import re
import socket
import sqlite3
import ssl
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, Request, Response, status

logger = logging.getLogger(__name__)

_UNIT_SECONDS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}

_RATE_RE = re.compile(r"^\s*(\d+)\s*/\s*([a-zA-Z]+)\s*$")
_REDIS_LUA_INCR = (
    "local c = redis.call('INCR', KEYS[1]); "
    "if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end; "
    "local t = redis.call('TTL', KEYS[1]); "
    "return {c, t}"
)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int


def parse_rate_limit(spec: str) -> Tuple[int, int]:
    """Parse rate string such as '20/minute' into (limit, window_seconds)."""
    match = _RATE_RE.match(spec or "")
    if not match:
        raise ValueError(f"Invalid rate limit specification: '{spec}'")
    limit = int(match.group(1))
    unit = match.group(2).lower()
    if limit < 1 or unit not in _UNIT_SECONDS:
        raise ValueError(f"Invalid rate limit specification: '{spec}'")
    return limit, _UNIT_SECONDS[unit]


def is_rate_limiting_enabled() -> bool:
    raw = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


_RENDER_DEFAULT_PROXY_CIDRS = (
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",
    "::1/128",
    "fc00::/7",
)

IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def get_trusted_proxy_networks() -> List[IPNetwork]:
    """
    Return trusted proxy networks from TRUSTED_PROXY_CIDRS, or Render's private/loopback
    edge proxy ranges when running under Render (RENDER=true). Returns [] otherwise so
    arbitrary X-Forwarded-For headers are never trusted on unverified direct connections.
    """
    raw = os.getenv("TRUSTED_PROXY_CIDRS", "").strip()
    if raw:
        cidrs = [item.strip() for item in raw.split(",") if item.strip()]
    elif os.getenv("RENDER", "").strip().lower() == "true":
        cidrs = list(_RENDER_DEFAULT_PROXY_CIDRS)
    else:
        return []

    networks: List[IPNetwork] = []
    for cidr in cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXY_CIDRS entry: '%s'", cidr)
    return networks


def _parse_ip(raw_ip: str) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
    try:
        return ipaddress.ip_address(raw_ip.strip())
    except ValueError:
        return None


def _is_trusted_proxy(ip_str: str, networks: List[IPNetwork]) -> bool:
    addr = _parse_ip(ip_str)
    if addr is None:
        return False
    return any(addr in net for net in networks)


def get_client_ip(request: Request) -> str:
    """
    Extract client IP using trusted-proxy verification.

    - Only inspects `X-Forwarded-For` when the direct TCP peer (`request.client.host`)
      belongs to a verified trusted proxy network (`TRUSTED_PROXY_CIDRS` or Render edge
      proxy when `RENDER=true`).
    - Walks `X-Forwarded-For` from right to left, stripping verified trusted proxy hops
      and returning the first untrusted valid client IP (preventing leftmost spoofing).
    - Falls back safely to `request.client.host` (or `"unknown"`) when the proxy chain
      is absent, unverified, or malformed.
    """
    peer_host = (
        request.client.host.strip()
        if request.client and request.client.host
        else ""
    )
    if not peer_host:
        return "unknown"

    trusted_networks = get_trusted_proxy_networks()
    if not trusted_networks or not _is_trusted_proxy(peer_host, trusted_networks):
        return peer_host

    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if not forwarded:
        return peer_host

    hops = [part.strip() for part in forwarded.split(",") if part.strip()]
    if not hops:
        return peer_host

    for hop in reversed(hops):
        parsed_hop = _parse_ip(hop)
        if parsed_hop is None:
            # Malformed hop invalidates forwarded chain; fall back safely to verified peer.
            return peer_host
        if not any(parsed_hop in net for net in trusted_networks):
            return str(parsed_hop)

    return peer_host


class MemoryFixedWindowBackend:
    """Thread-safe in-memory fixed-window store (single-process / testing)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, Tuple[int, int]] = {}

    def increment(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        window_id = now // window_seconds
        reset_at = (window_id + 1) * window_seconds
        retry_after = max(1, reset_at - now)
        bucket_key = f"{key}:{window_id}"

        with self._lock:
            if len(self._buckets) > 4096:
                stale = [k for k, (_, exp) in self._buckets.items() if exp <= now]
                for k in stale:
                    del self._buckets[k]
            count, _ = self._buckets.get(bucket_key, (0, reset_at))
            count += 1
            self._buckets[bucket_key] = (count, reset_at)

        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            reset_at=reset_at,
            retry_after=retry_after,
        )

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


class SQLiteFixedWindowBackend:
    """Cross-process SQLite WAL fixed-window store shared across Uvicorn workers."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rate_limit_buckets (
                        bucket_key TEXT PRIMARY KEY,
                        hit_count INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL
                    );
                    """
                )

    def increment(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        window_id = now // window_seconds
        reset_at = (window_id + 1) * window_seconds
        retry_after = max(1, reset_at - now)
        bucket_key = f"{key}:{window_id}"

        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute("DELETE FROM rate_limit_buckets WHERE expires_at <= ?;", (now,))
                conn.execute(
                    """
                    INSERT INTO rate_limit_buckets (bucket_key, hit_count, expires_at)
                    VALUES (?, 1, ?)
                    ON CONFLICT(bucket_key) DO UPDATE SET
                        hit_count = rate_limit_buckets.hit_count + 1,
                        expires_at = excluded.expires_at;
                    """,
                    (bucket_key, reset_at),
                )
                row = conn.execute(
                    "SELECT hit_count FROM rate_limit_buckets WHERE bucket_key = ?;",
                    (bucket_key,),
                ).fetchone()
                conn.execute("COMMIT;")
                count = int(row[0]) if row else 1
            except Exception:
                try:
                    conn.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            reset_at=reset_at,
            retry_after=retry_after,
        )

    def clear(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM rate_limit_buckets;")
            finally:
                conn.close()


def _resp_encode_command(*parts: str) -> bytes:
    chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
    for part in parts:
        data = str(part).encode("utf-8")
        chunks.append(f"${len(data)}\r\n".encode("utf-8"))
        chunks.append(data + b"\r\n")
    return b"".join(chunks)


def _resp_read_reply(sock_file) -> object:
    line = sock_file.readline()
    if not line:
        raise ConnectionError("Unexpected EOF from Redis rate-limit server.")
    prefix = chr(line[0])
    payload = line[1:].rstrip(b"\r\n")
    if prefix == "+":
        return payload.decode("utf-8", errors="replace")
    if prefix == "-":
        raise RuntimeError(f"Redis error: {payload.decode('utf-8', errors='replace')}")
    if prefix == ":":
        return int(payload)
    if prefix == "$":
        length = int(payload)
        if length == -1:
            return None
        data = sock_file.read(length + 2)
        return data[:-2].decode("utf-8", errors="replace")
    if prefix == "*":
        count = int(payload)
        if count == -1:
            return None
        return [_resp_read_reply(sock_file) for _ in range(count)]
    raise RuntimeError(f"Unsupported RESP prefix: {prefix!r}")


class RedisFixedWindowBackend:
    """Minimal RESP2 Redis fixed-window store for multi-instance deployments."""

    def __init__(self, redis_url: str, timeout_seconds: float = 2.0) -> None:
        self.redis_url = redis_url
        self.timeout_seconds = timeout_seconds

    def _open_socket(self) -> socket.socket:
        parsed = urlparse(self.redis_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        raw_sock = socket.create_connection((host, port), timeout=self.timeout_seconds)
        if parsed.scheme.lower() == "rediss":
            ctx = ssl.create_default_context()
            return ctx.wrap_socket(raw_sock, server_hostname=host)
        return raw_sock

    def increment(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        window_id = now // window_seconds
        reset_at = (window_id + 1) * window_seconds
        bucket_key = f"rl:{key}:{window_id}"
        parsed = urlparse(self.redis_url)
        username = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None
        db_num = parsed.path.lstrip("/") if parsed.path and parsed.path != "/" else None

        with self._open_socket() as sock:
            sock_file = sock.makefile("rb")
            if password:
                if username:
                    sock.sendall(_resp_encode_command("AUTH", username, password))
                else:
                    sock.sendall(_resp_encode_command("AUTH", password))
                _resp_read_reply(sock_file)
            if db_num and db_num.isdigit() and int(db_num) != 0:
                sock.sendall(_resp_encode_command("SELECT", db_num))
                _resp_read_reply(sock_file)

            sock.sendall(
                _resp_encode_command(
                    "EVAL", _REDIS_LUA_INCR, "1", bucket_key, str(window_seconds)
                )
            )
            reply = _resp_read_reply(sock_file)

        if not isinstance(reply, list) or len(reply) < 2:
            raise RuntimeError("Unexpected Redis EVAL reply for rate limiter.")
        count = int(reply[0])
        ttl = int(reply[1]) if int(reply[1]) > 0 else max(1, reset_at - now)
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            reset_at=now + ttl,
            retry_after=max(1, ttl),
        )


_backend_lock = threading.Lock()
_cached_uri: Optional[str] = None
_cached_backend: Optional[object] = None
_fallback_sqlite: Optional[SQLiteFixedWindowBackend] = None


def resolve_storage_uri() -> str:
    """Resolve rate-limit backend URI from RATE_LIMIT_STORAGE_URI or REDIS_URL."""
    explicit = os.getenv("RATE_LIMIT_STORAGE_URI", "").strip()
    if explicit:
        return explicit
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        return redis_url
    default_path = Path(tempfile.gettempdir()) / "cricketgpt_ratelimit.sqlite3"
    return f"sqlite:///{default_path.as_posix()}"


def _get_backend():
    global _cached_uri, _cached_backend, _fallback_sqlite
    uri = resolve_storage_uri()
    with _backend_lock:
        if _cached_backend is not None and _cached_uri == uri:
            return _cached_backend

        lower = uri.lower()
        if lower.startswith(("redis://", "rediss://")):
            _cached_backend = RedisFixedWindowBackend(uri)
        elif lower.startswith("memory://"):
            _cached_backend = MemoryFixedWindowBackend()
        elif lower.startswith("sqlite:///"):
            raw_path = uri[len("sqlite:///") :]
            _cached_backend = SQLiteFixedWindowBackend(raw_path)
        else:
            default_path = Path(tempfile.gettempdir()) / "cricketgpt_ratelimit.sqlite3"
            _cached_backend = SQLiteFixedWindowBackend(default_path)

        _cached_uri = uri
        return _cached_backend


def _get_fallback_sqlite() -> SQLiteFixedWindowBackend:
    global _fallback_sqlite
    with _backend_lock:
        if _fallback_sqlite is None:
            default_path = Path(tempfile.gettempdir()) / "cricketgpt_ratelimit.sqlite3"
            _fallback_sqlite = SQLiteFixedWindowBackend(default_path)
        return _fallback_sqlite


def reset_rate_limiter() -> None:
    """Clear in-memory / SQLite rate-limit state (intended for unit tests)."""
    global _cached_uri, _cached_backend, _fallback_sqlite
    with _backend_lock:
        for backend in (_cached_backend, _fallback_sqlite):
            clear_fn = getattr(backend, "clear", None)
            if callable(clear_fn):
                clear_fn()
        _cached_uri = None
        _cached_backend = None
        _fallback_sqlite = None


def check_rate_limit(bucket: str, env_var: str, default_spec: str, request: Request, response: Response) -> None:
    """Enforce configured fixed-window rate limit for a request."""
    if not is_rate_limiting_enabled():
        return

    raw_spec = os.getenv(env_var, default_spec).strip() or default_spec
    try:
        limit, window_seconds = parse_rate_limit(raw_spec)
    except ValueError:
        logger.warning("Invalid %s='%s'; falling back to %s.", env_var, raw_spec, default_spec)
        limit, window_seconds = parse_rate_limit(default_spec)

    client_ip = get_client_ip(request)
    key = f"{bucket}:{client_ip}"
    backend = _get_backend()

    try:
        result = backend.increment(key, limit=limit, window_seconds=window_seconds)
    except Exception as exc:
        if isinstance(backend, RedisFixedWindowBackend):
            logger.warning(
                "Redis rate-limit backend error (%s); falling back to local SQLite store.",
                type(exc).__name__,
            )
            result = _get_fallback_sqlite().increment(
                key, limit=limit, window_seconds=window_seconds
            )
        else:
            raise

    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(result.reset_at),
    }
    for header_name, header_val in headers.items():
        response.headers[header_name] = header_val

    if not result.allowed:
        headers["Retry-After"] = str(result.retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers=headers,
        )


def rate_limit_dependency(bucket: str, env_var: str, default_spec: str):
    """Create a FastAPI dependency that enforces the named rate limit."""

    def _dependency(request: Request, response: Response) -> None:
        check_rate_limit(
            bucket=bucket,
            env_var=env_var,
            default_spec=default_spec,
            request=request,
            response=response,
        )

    return _dependency


rate_limit_chat = rate_limit_dependency("chat", "RATE_LIMIT_CHAT", "20/minute")
rate_limit_rag_search = rate_limit_dependency("rag_search", "RATE_LIMIT_RAG_SEARCH", "60/minute")
rate_limit_rag_ingest = rate_limit_dependency("rag_ingest", "RATE_LIMIT_RAG_INGEST", "10/minute")

