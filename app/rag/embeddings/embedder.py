"""
CricketGPT — Google Gemini Embeddings Service

Uses Google Gen AI SDK (`google-genai`) with `gemini-embedding-2` (768 dimensions)
and supports:
- Explicit `RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY` task types
- Configurable `output_dimensionality` (default 768) with L2 normalization
- Batch embedding with per-item length verification
- Request timeout configuration via `AI_TIMEOUT`
- Exponential-backoff retries for transient failures
- Thread-safe SHA-256 keyed LRU cache
- Strict error handling (no silent fallback to Sentence Transformers)
"""

import hashlib
import logging
import math
import os
import threading
import time
from collections import OrderedDict
from typing import Callable, List, Optional, TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "gemini-embedding-2").strip()
EMBEDDING_DIMENSION = int(os.getenv("RAG_EMBEDDING_DIMENSION", "768"))

_PLACEHOLDER_PREFIXES = ("your_", "your-", "<your")

T = TypeVar("T")


def _is_placeholder(value: str) -> bool:
    lower = value.strip().lower()
    return any(lower.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _l2_normalize(vector: List[float]) -> List[float]:
    """L2-normalize a vector so cosine distance works accurately after dimension truncation."""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return list(vector)
    return [float(v / norm) for v in vector]


_TRANSIENT_GEMINI_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable_gemini_error(exc: Exception) -> bool:
    """
    Return True for transient network/rate-limit/5xx Gemini errors and False for
    permanent authentication (401/403), invalid-argument (400), or config errors.
    """
    if isinstance(exc, ValueError):
        return False
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code in _TRANSIENT_GEMINI_HTTP_CODES
    msg = str(exc).lower()
    if "gemini_api_key is missing" in msg or "placeholder value" in msg:
        return False
    return True


def retry_with_backoff(
    fn: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 0.5,
    operation_name: str = "operation",
    is_retryable: Optional[Callable[[Exception], bool]] = None,
) -> T:
    """Execute `fn` with exponential backoff on retryable transient failures."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            can_retry = is_retryable(exc) if is_retryable is not None else True
            if attempt >= max_attempts or not can_retry:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "%s failed (attempt %d/%d: %s). Retrying in %.2fs...",
                operation_name,
                attempt,
                max_attempts,
                type(exc).__name__,
                delay,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


class EmbeddingService:
    """Thread-safe Google Gemini embedder with LRU cache, batching, and backoff retries."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = EMBEDDING_DIMENSION,
        cache_size: int = 2048,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        if not model_name or not model_name.strip() or _is_placeholder(model_name):
            raise ValueError(f"Invalid Gemini embedding model configuration: '{model_name}'")
        if dimension <= 0 or dimension > 2000:
            raise ValueError(
                "RAG embedding dimension must be between 1 and 2000 for pgvector HNSW indexing."
            )
        self.model_name = model_name.strip()
        self.dimension = dimension
        self.cache_size = cache_size
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else int(os.getenv("AI_TIMEOUT", "30"))
        )
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, List[float]] = OrderedDict()

    def _get_api_key(self) -> str:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key or _is_placeholder(api_key):
            raise RuntimeError(
                "GEMINI_API_KEY is missing or is a placeholder value. "
                "Configure a valid GEMINI_API_KEY in your environment."
            )
        return api_key

    def _cache_key(self, text: str, task_type: str) -> str:
        raw = f"{self.model_name}:{self.dimension}:{task_type}:{text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _cache_get(self, key: str) -> Optional[List[float]]:
        with self._lock:
            vec = self._cache.get(key)
            if vec is not None:
                self._cache.move_to_end(key)
            return vec

    def _cache_put(self, key: str, vector: List[float]) -> None:
        if self.cache_size <= 0:
            return
        with self._lock:
            self._cache[key] = vector
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def cache_stats(self) -> dict:
        with self._lock:
            return {
                "model": self.model_name,
                "dimension": self.dimension,
                "cached_entries": len(self._cache),
                "max_size": self.cache_size,
            }

    def _call_gemini_embed(
        self,
        texts: List[str],
        task_type: str,
    ) -> List[List[float]]:
        api_key = self._get_api_key()
        timeout_ms = max(1000, int(self.timeout_seconds) * 1000)

        contents = [
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in texts
        ]
        config = types.EmbedContentConfig(
            output_dimensionality=self.dimension,
            task_type=task_type,
        )

        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        ) as client:
            response = client.models.embed_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )

        embeddings = getattr(response, "embeddings", None) or []
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Gemini embedding response count mismatch: expected {len(texts)}, got {len(embeddings)}."
            )

        normalized_vectors: List[List[float]] = []
        for idx, item in enumerate(embeddings):
            vals = list(getattr(item, "values", None) or [])
            if len(vals) != self.dimension:
                raise RuntimeError(
                    f"Gemini embedding dimension mismatch at index {idx}: "
                    f"expected {self.dimension}, got {len(vals)}."
                )
            normalized_vectors.append(_l2_normalize([float(x) for x in vals]))

        return normalized_vectors

    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 32,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> List[List[float]]:
        """
        Generate L2-normalized Gemini embeddings for a batch of texts,
        checking the LRU cache first and retrying transient API errors with backoff.
        """
        if not texts:
            return []
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        results: List[Optional[List[float]]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []
        missing_keys: List[str] = []

        for idx, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Cannot embed empty text at batch index {idx}.")
            key = self._cache_key(text, task_type)
            cached = self._cache_get(key)
            if cached is not None:
                results[idx] = cached
            else:
                missing_indices.append(idx)
                missing_texts.append(text)
                missing_keys.append(key)

        for start in range(0, len(missing_texts), batch_size):
            batch_texts = missing_texts[start : start + batch_size]
            batch_indices = missing_indices[start : start + batch_size]
            batch_keys = missing_keys[start : start + batch_size]

            computed = retry_with_backoff(
                lambda bt=batch_texts: self._call_gemini_embed(bt, task_type=task_type),
                max_attempts=3,
                base_delay=0.5,
                operation_name=f"Gemini embed_content ({self.model_name})",
                is_retryable=is_retryable_gemini_error,
            )

            for idx, key, vec in zip(batch_indices, batch_keys, computed):
                self._cache_put(key, vec)
                results[idx] = vec

        return [vec for vec in results if vec is not None]

    def embed_query(self, query: str) -> List[float]:
        """Embed a single retrieval query using RETRIEVAL_QUERY task type."""
        if not query or not query.strip():
            raise ValueError("Query text cannot be empty.")
        return self.embed_texts(
            [query.strip()],
            batch_size=1,
            task_type="RETRIEVAL_QUERY",
        )[0]


_default_embedder: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Return shared process-level Gemini EmbeddingService instance."""
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = EmbeddingService()
    return _default_embedder
