"""
Offline/mock evaluation runner CLI for CricketGPT Phase 4.

NOTE:
Only `--mode mock` is supported while `task-1563` historical RAG backfill is running.
Live Supabase/Gemini tracing is intentionally disabled until authorized.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation.dataset import filter_benchmark_cases, load_benchmark_dataset
from app.evaluation.scorer import evaluate_dataset, save_evaluation_reports
from app.evaluation.tracer import MockFixtureExecutor, build_default_offline_fixtures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CricketGPT chatbot evaluation (offline/mock mode)."
    )
    parser.add_argument(
        "--mode",
        choices=["mock"],
        default="mock",
        help="Execution mode (only 'mock' is active in this offline phase).",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Optional custom path to benchmark JSON dataset.",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
        help="Optional category filters (historical, recent, statistics, narrative, edge_case).",
    )
    parser.add_argument(
        "--verified-only",
        action="store_true",
        help="Evaluate only cases whose ground truth is already verified.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "evaluation" / "reports"),
        help="Directory where JSON and Markdown reports will be saved.",
    )
    args = parser.parse_args()

    cases = load_benchmark_dataset(args.dataset)
    cases = filter_benchmark_cases(
        cases,
        categories=args.categories,
        verified_only=args.verified_only,
    )

    executor = MockFixtureExecutor(build_default_offline_fixtures())
    eval_output = evaluate_dataset(cases, executor)
    summary = eval_output["summary"]
    results = eval_output["results"]

    written = save_evaluation_reports(
        summary=summary,
        results=results,
        output_dir=args.output_dir,
        mode_label="offline_mock",
    )

    print(
        json.dumps(
            {
                "mode": args.mode,
                "summary": summary.model_dump(),
                "reports": {k: str(v) for k, v in written.items()},
            },
            indent=2,
        )
    )
    return 0 if summary.incorrect == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

