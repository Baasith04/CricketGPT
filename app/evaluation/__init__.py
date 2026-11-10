"""CricketGPT standalone evaluation package (offline/mock framework)."""

from app.evaluation.dataset import BenchmarkCase, EvaluationDataset, load_benchmark_dataset
from app.evaluation.scorer import (
    CaseEvaluationResult,
    EvaluationSummary,
    evaluate_case,
    evaluate_dataset,
    render_markdown_report,
    save_evaluation_reports,
    summarize_evaluations,
)
from app.evaluation.tracer import (
    AbstractChatExecutor,
    ChatExecutionTrace,
    MockFixtureExecutor,
    RagChunkTrace,
    SqlEvidenceTrace,
)

__all__ = [
    "AbstractChatExecutor",
    "BenchmarkCase",
    "CaseEvaluationResult",
    "ChatExecutionTrace",
    "EvaluationDataset",
    "EvaluationSummary",
    "MockFixtureExecutor",
    "RagChunkTrace",
    "SqlEvidenceTrace",
    "evaluate_case",
    "evaluate_dataset",
    "load_benchmark_dataset",
    "render_markdown_report",
    "save_evaluation_reports",
    "summarize_evaluations",
]

