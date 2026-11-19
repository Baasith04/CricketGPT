"""
CricketGPT — RAG Text Extraction, Cleaning, Recursive Chunking & Metadata Assignment
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

VALID_DOC_TYPES = {
    "match_report",
    "season_summary",
    "player_profile",
    "team_history",
    "cricket_rule",
    "general_knowledge",
}


def compute_sha256(text: str) -> str:
    """Compute SHA-256 hex digest for UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    """
    Normalize text for chunking and embedding:
    - Strip NUL/control characters (keeping newlines and tabs)
    - Collapse trailing spaces per line
    - Normalize 3+ consecutive newlines to paragraph breaks
    """
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _parse_frontmatter(raw_text: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse optional simple YAML-style `---` frontmatter header at the top of Markdown/text files.
    Returns (metadata_dict, body_text).
    """
    stripped = raw_text.lstrip("\ufeff")
    if not stripped.startswith("---\n"):
        return {}, raw_text

    end_idx = stripped.find("\n---\n", 4)
    if end_idx == -1:
        return {}, raw_text

    header = stripped[4:end_idx]
    body = stripped[end_idx + 5 :]
    meta: Dict[str, Any] = {}

    for line in header.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        k = key.strip().lower()
        v = val.strip()
        if not v:
            continue
        if v.startswith("[") and v.endswith("]"):
            items = [item.strip().strip("\"'") for item in v[1:-1].split(",") if item.strip()]
            meta[k] = items
        elif k == "match_id" and v.isdigit():
            meta[k] = int(v)
        else:
            meta[k] = v.strip("\"'")

    return meta, body


def extract_text_from_file(file_path: str | Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text and optional embedded metadata from .md, .txt, .json, or .pdf files.
    Rejects raw Cricsheet ball-by-ball JSON archives so individual deliveries are not embedded.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()
    if suffix in (".md", ".markdown", ".txt"):
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        return clean_text(body), meta

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "innings" in payload and "info" in payload:
            raise ValueError(
                f"Refusing to chunk raw Cricsheet ball-by-ball file '{path.name}' directly."
            )
        if isinstance(payload, dict):
            text = payload.get("content") or payload.get("text") or json.dumps(payload, indent=2)
            meta = {
                k: v for k, v in payload.items()
                if k not in ("content", "text")
            }
            return clean_text(str(text)), meta
        return clean_text(json.dumps(payload, indent=2)), {}

    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return clean_text("\n\n".join(pages)), {"page_count": len(reader.pages)}

    raise ValueError(f"Unsupported document format: '{suffix}'")


def recursive_chunk_text(
    text: str,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
    separators: Optional[List[str]] = None,
) -> List[str]:
    """
    Recursively split `text` into chunks up to `chunk_size` characters with
    up to `chunk_overlap` characters of context overlap between consecutive chunks.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size.")

    cleaned = clean_text(text)
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    seps = separators if separators is not None else list(DEFAULT_SEPARATORS)

    def _split(segment: str, sep_list: List[str]) -> List[str]:
        if len(segment) <= chunk_size:
            return [segment]

        if not sep_list:
            return [
                segment[i : i + chunk_size]
                for i in range(0, len(segment), chunk_size - chunk_overlap)
            ]

        sep = sep_list[0]
        rest = sep_list[1:]

        if sep == "":
            return [
                segment[i : i + chunk_size]
                for i in range(0, len(segment), chunk_size - chunk_overlap)
            ]

        parts = segment.split(sep)
        if len(parts) == 1:
            return _split(segment, rest)

        merged: List[str] = []
        current = ""

        for part in parts:
            piece = part.strip() if sep.strip() == "" else part
            if not piece:
                continue
            candidate = f"{current}{sep}{piece}" if current else piece

            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    merged.append(current.strip())
                if len(piece) > chunk_size:
                    merged.extend(_split(piece, rest))
                    current = ""
                else:
                    current = piece

        if current:
            merged.append(current.strip())

        return [m for m in merged if m]

    raw_chunks = _split(cleaned, seps)
    if chunk_overlap == 0 or len(raw_chunks) <= 1:
        return raw_chunks

    overlapped: List[str] = [raw_chunks[0]]
    for idx in range(1, len(raw_chunks)):
        prev = raw_chunks[idx - 1]
        tail = prev[-chunk_overlap:].lstrip()
        curr = raw_chunks[idx]
        if tail and not curr.startswith(tail):
            combined = f"{tail}\n{curr}" if len(tail) + len(curr) + 1 <= chunk_size + chunk_overlap else curr
        else:
            combined = curr
        overlapped.append(combined)

    return overlapped


def prepare_document_chunks(
    text: str,
    source_key: str,
    title: str,
    doc_type: str = "general_knowledge",
    season: Optional[str] = None,
    match_id: Optional[int] = None,
    teams: Optional[List[str]] = None,
    players: Optional[List[str]] = None,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    Clean, recursively chunk, and attach structured metadata to each chunk.
    """
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(
            f"Unsupported doc_type '{doc_type}'. Must be one of: {', '.join(sorted(VALID_DOC_TYPES))}."
        )

    chunks = recursive_chunk_text(
        text=text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    total = len(chunks)
    teams_list = list(teams or [])
    players_list = list(players or [])

    prepared: List[Dict[str, Any]] = []
    for idx, chunk_text in enumerate(chunks):
        meta: Dict[str, Any] = {
            "source_key": source_key,
            "title": title,
            "doc_type": doc_type,
            "chunk_index": idx,
            "total_chunks": total,
        }
        if season:
            meta["season"] = season
        if match_id is not None:
            meta["match_id"] = match_id
        if teams_list:
            meta["teams"] = teams_list
        if players_list:
            meta["players"] = players_list
        if source_path:
            meta["source_path"] = source_path
        if source_url:
            meta["source_url"] = source_url
        if extra_metadata:
            meta.update(extra_metadata)

        prepared.append(
            {
                "chunk_index": idx,
                "chunk_text": chunk_text,
                "chunk_sha256": compute_sha256(chunk_text),
                "token_estimate": max(1, len(chunk_text.split())),
                "doc_type": doc_type,
                "season": season,
                "match_id": match_id,
                "metadata": meta,
            }
        )

    return prepared

