"""
CLI tool to apply the pgvector RAG migration and ingest documents / DB match summaries / historical backfill.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.embeddings.embedder import DailyQuotaExhaustedError
from app.rag.pipeline.rag_pipeline import (
    apply_gemini_embedding_migration,
    apply_rag_migration,
    backfill_historical_match_rag,
    ingest_db_match_summaries,
    ingest_directory,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply RAG pgvector schema and ingest IPL knowledge documents."
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Execute 002_rag_pgvector_schema.sql (non-destructive IF NOT EXISTS).",
    )
    parser.add_argument(
        "--migrate-gemini",
        action="store_true",
        help="Safely migrate 384-d chunks to 768-d Gemini embeddings and re-embed all existing chunks.",
    )
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default=None,
        help="Directory of .md/.txt/.json/.pdf files to ingest.",
    )
    parser.add_argument(
        "--match-summaries",
        action="store_true",
        help="Generate and ingest high-level match summaries from Supabase matches.",
    )
    parser.add_argument(
        "--backfill-rag",
        action="store_true",
        help="Safely & resumably backfill missing db:match:<id> RAG summaries across stored IPL matches.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="When combined with --backfill-rag, report missing match counts without writing.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for historical RAG backfill (default 50).",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Optional cap on matches processed in a backfill run.",
    )
    parser.add_argument(
        "--seasons",
        nargs="*",
        default=None,
        help="Optional season filters for match summaries / backfill (e.g. 2024 2023).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max DB match summaries to generate with --match-summaries (default 100).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-chunking and re-embedding even if content SHA-256 is unchanged.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    output = {}
    exit_code = 0

    try:
        if args.migrate:
            apply_rag_migration()
            output["migration"] = "applied"

        if args.migrate_gemini:
            output["gemini_migration"] = apply_gemini_embedding_migration()

        if args.knowledge_dir:
            output["directory_ingestion"] = ingest_directory(
                directory=args.knowledge_dir,
                force=args.force,
            )

        if args.match_summaries:
            output["match_summaries"] = ingest_db_match_summaries(
                seasons=args.seasons,
                limit=args.limit,
                force=args.force,
            )

        if args.backfill_rag:
            backfill_res = backfill_historical_match_rag(
                batch_size=args.batch_size,
                seasons=args.seasons,
                max_matches=args.max_matches,
                force=args.force,
                dry_run=args.dry_run,
            )
            output["backfill_rag"] = backfill_res
            if backfill_res.get("quota_exhausted"):
                exit_code = 2
                logging.getLogger(__name__).error(
                    "Backfill paused due to Gemini daily quota exhaustion. "
                    "Remaining matches: %s. Resume after quota recovery with: %s",
                    backfill_res.get("remaining_matches"),
                    backfill_res.get("resume_command"),
                )
    except DailyQuotaExhaustedError as exc:
        output["quota_exhausted"] = True
        output["error"] = str(exc)
        exit_code = 2

    print(json.dumps(output, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
