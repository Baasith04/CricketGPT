"""Pydantic schemas for CricketGPT Hybrid RAG ingestion and search endpoints."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


DocTypeLiteral = Literal[
    "match_report",
    "season_summary",
    "player_profile",
    "team_history",
    "cricket_rule",
    "general_knowledge",
]


class RagIngestRequest(BaseModel):
    source_key: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=10)
    doc_type: DocTypeLiteral = "general_knowledge"
    season: Optional[str] = Field(default=None, max_length=15)
    match_id: Optional[int] = Field(default=None, ge=1)
    teams: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: int = Field(default=700, ge=100, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)
    force: bool = False


class RagIngestResponse(BaseModel):
    source_key: str
    doc_id: int
    status: str
    chunk_count: int


class RagDirectoryIngestRequest(BaseModel):
    directory: str = Field(..., min_length=1)
    default_doc_type: DocTypeLiteral = "general_knowledge"
    force: bool = False


class RagMatchSummariesIngestRequest(BaseModel):
    seasons: Optional[List[str]] = None
    match_ids: Optional[List[int]] = None
    limit: int = Field(default=100, ge=1, le=2000)
    force: bool = False


class RagSearchChunk(BaseModel):
    chunk_id: int
    doc_id: int
    source_key: str
    title: str
    doc_type: str
    season: Optional[str] = None
    match_id: Optional[int] = None
    teams: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    chunk_index: int
    chunk_text: str
    vector_similarity: float
    keyword_score: float
    hybrid_score: float


class RagSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[RagSearchChunk]

