"""CLI entry point for scheduled or manual Cricsheet IPL synchronization."""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when invoked as `python scripts/run_sync.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.sync.sync_runner import retry_failed_rag_sync, run_sync


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize IPL matches from Cricsheet into Supabase SQL & RAG."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for new/changed matches without writing to the database.",
    )
    parser.add_argument(
        "--triggered-by",
        default="cron",
        choices=["cron", "manual", "initial_import"],
        help="Trigger source recorded in sync_history.",
    )
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Skip incremental RAG match summary ingestion after SQL sync.",
    )
    parser.add_argument(
        "--retry-rag",
        action="store_true",
        help="Retry failed RAG ingestion from a previous sync_history record.",
    )
    parser.add_argument(
        "--sync-id",
        type=int,
        default=None,
        help="Specific sync_id to inspect when used with --retry-rag.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.retry_rag:
        summary = retry_failed_rag_sync(
            sync_id=args.sync_id,
            triggered_by=args.triggered_by,
        )
    else:
        summary = run_sync(
            dry_run=args.dry_run,
            triggered_by=args.triggered_by,
            sync_rag=not args.skip_rag,
        )

    print(json.dumps(summary, indent=2, default=str))

    if summary.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
