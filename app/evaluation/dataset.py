"""Benchmark dataset loader and schema definitions for CricketGPT evaluation."""

import json
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

DEFAULT_BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "evaluation"
    / "datasets"
    / "ipl_benchmark.json"
)

CategoryLiteral = Literal[
    "historical",
    "recent",
    "statistics",
    "narrative",
    "edge_case",
]

GroundTruthStatusLiteral = Literal["verified", "pending_verification"]


class BenchmarkCase(BaseModel):
    """Single structured evaluation question with expected routing and ground-truth checks."""

    id: str = Field(..., min_length=1)
    category: CategoryLiteral
    question: str = Field(..., min_length=1)
    expected_route: str = Field(..., min_length=1)
    expected_cutoff_scope: Optional[str] = None
    requires_sql: bool = False
    requires_rag: bool = False
    expected_rag_season: Optional[str] = None
    expected_rag_doc_type: Optional[str] = None
    expected_rag_match_id: Optional[int] = None
    must_refuse_or_clarify: bool = False
    expected_citations: List[str] = Field(default_factory=list)
    required_facts: List[str] = Field(default_factory=list)
    required_numbers: List[str] = Field(default_factory=list)
    forbidden_patterns: List[str] = Field(default_factory=list)
    ground_truth_status: GroundTruthStatusLiteral = "pending_verification"
    notes: Optional[str] = None


class EvaluationDataset(BaseModel):
    """Root container for a versioned JSON benchmark dataset."""

    dataset_version: str
    description: str
    cases: List[BenchmarkCase] = Field(default_factory=list)


def load_benchmark_dataset(path: Optional[Path | str] = None) -> List[BenchmarkCase]:
    """Load and validate benchmark evaluation cases from JSON."""
    target = Path(path) if path else DEFAULT_BENCHMARK_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Benchmark dataset not found: {target}")

    payload = json.loads(target.read_text(encoding="utf-8"))
    parsed = EvaluationDataset(**payload)
    return parsed.cases


def filter_benchmark_cases(
    cases: List[BenchmarkCase],
    categories: Optional[List[str]] = None,
    verified_only: bool = False,
) -> List[BenchmarkCase]:
    """Filter benchmark cases cleanly by category and verification status."""
    filtered = cases
    if categories:
        allowed = {c.strip().lower() for c in categories if c.strip()}
        filtered = [c for c in filtered if c.category.lower() in allowed]
    if verified_only:
        filtered = [c for c in filtered if c.ground_truth_status == "verified"]
    return filtered

