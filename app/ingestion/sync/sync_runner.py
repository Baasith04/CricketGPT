import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from psycopg.types.json import Jsonb

from app.database.connection import get_db_connection
from app.ingestion.importer import import_match
from app.ingestion.sync.cricsheet_client import (
    download_ipl_archive,
    scan_ipl_archive,
)
from app.ingestion.sync.sync_planner import create_sync_plan
from app.ingestion.validators.scorecard_validator import validate_imported_match
from app.rag.pipeline.rag_pipeline import ingest_db_match_summaries

logger = logging.getLogger(__name__)

VALID_TRIGGERS = {"cron", "manual", "initial_import"}


def _insert_sync_history(triggered_by: str) -> int:
    """Insert an initial 'running' row in sync_history and return its sync_id."""
    query = """
        INSERT INTO sync_history (triggered_by, status)
        VALUES (%s, 'running')
        RETURNING sync_id;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (triggered_by,))
            sync_id = cur.fetchone()[0]
        conn.commit()
    return sync_id


def _update_sync_history(
    sync_id: int,
    status: str,
    files_checked: int = 0,
    files_downloaded: int = 0,
    matches_inserted: int = 0,
    matches_updated: int = 0,
    matches_skipped: int = 0,
    matches_failed: int = 0,
    error_details: Optional[Any] = None,
) -> None:
    """Finalize a sync_history row with status, counts, and optional error details."""
    query = """
        UPDATE sync_history
        SET completed_at = NOW(),
            status = %s,
            files_checked = %s,
            files_downloaded = %s,
            matches_inserted = %s,
            matches_updated = %s,
            matches_skipped = %s,
            matches_failed = %s,
            error_details = %s
        WHERE sync_id = %s;
    """
    payload = Jsonb(error_details) if error_details is not None else None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    status,
                    files_checked,
                    files_downloaded,
                    matches_inserted,
                    matches_updated,
                    matches_skipped,
                    matches_failed,
                    payload,
                    sync_id,
                ),
            )
        conn.commit()


def _extract_failed_rag_match_ids(error_details: Any) -> List[int]:
    """Extract failed RAG match IDs from a stored `sync_history.error_details` payload."""
    items = []
    if isinstance(error_details, list):
        items = error_details
    elif isinstance(error_details, dict):
        items = error_details.get("errors") or []

    match_ids: List[int] = []
    for entry in items:
        if not isinstance(entry, dict) or entry.get("stage") != "rag":
            continue
        mid = entry.get("match_id")
        if isinstance(mid, int) and not isinstance(mid, bool) and mid > 0:
            match_ids.append(mid)
        for batch_mid in entry.get("match_ids") or []:
            if isinstance(batch_mid, int) and not isinstance(batch_mid, bool) and batch_mid > 0:
                match_ids.append(batch_mid)
    return list(dict.fromkeys(match_ids))


def retry_failed_rag_sync(
    sync_id: Optional[int] = None,
    match_ids: Optional[List[int]] = None,
    triggered_by: str = "manual",
) -> Dict[str, Any]:
    """
    Retry failed RAG match-summary ingestion for a prior `sync_history` entry
    (or explicit match IDs) without re-downloading or rewriting SQL tables.
    """
    if triggered_by not in VALID_TRIGGERS:
        raise ValueError(
            f"Invalid triggered_by '{triggered_by}'. "
            f"Must be one of: {', '.join(sorted(VALID_TRIGGERS))}."
        )

    target_ids: List[int] = []
    source_sync_id: Optional[int] = sync_id

    if match_ids is not None:
        target_ids = list(
            dict.fromkeys(
                int(mid) for mid in match_ids
                if isinstance(mid, int) and not isinstance(mid, bool) and mid > 0
            )
        )
    else:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if sync_id is not None:
                    cur.execute(
                        "SELECT sync_id, error_details FROM sync_history WHERE sync_id = %s;",
                        (sync_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        source_sync_id = row[0]
                        target_ids = _extract_failed_rag_match_ids(row[1])
                else:
                    cur.execute(
                        """
                        SELECT sync_id, error_details
                        FROM sync_history
                        WHERE error_details IS NOT NULL
                        ORDER BY sync_id DESC
                        LIMIT 20;
                        """
                    )
                    for row in cur.fetchall():
                        found = _extract_failed_rag_match_ids(row[1])
                        if found:
                            source_sync_id = row[0]
                            target_ids = found
                            break

    if not target_ids:
        return {
            "source_sync_id": source_sync_id,
            "sync_id": None,
            "status": "no_failed_rag_matches",
            "retried_match_ids": [],
            "rag_ingested": 0,
            "rag_updated": 0,
            "rag_unchanged": 0,
            "rag_failed": 0,
            "rag_failed_match_ids": [],
        }

    retry_sync_id = _insert_sync_history(triggered_by)
    errors: List[Dict[str, Any]] = []
    rag_counts = {"ingested": 0, "updated": 0, "unchanged": 0, "failed": 0}
    rag_failed_ids: List[int] = []

    try:
        rag_result = ingest_db_match_summaries(match_ids=target_ids)
        rag_counts = rag_result["counts"]
        rag_failed_ids = rag_result.get("failed_match_ids", [])
        for err in rag_result.get("errors", []):
            errors.append({"stage": "rag", **err})
    except Exception as exc:
        logger.error("RAG retry ingestion failed: %s", exc)
        rag_counts["failed"] = len(target_ids)
        rag_failed_ids = list(target_ids)
        errors.append(
            {
                "stage": "rag",
                "match_ids": list(target_ids),
                "error": str(exc),
            }
        )

    final_status = "partial_failure" if rag_failed_ids else "success"
    _update_sync_history(
        sync_id=retry_sync_id,
        status=final_status,
        files_checked=len(target_ids),
        error_details=errors if errors else None,
    )

    return {
        "source_sync_id": source_sync_id,
        "sync_id": retry_sync_id,
        "status": final_status,
        "retried_match_ids": target_ids,
        "rag_ingested": rag_counts["ingested"],
        "rag_updated": rag_counts["updated"],
        "rag_unchanged": rag_counts["unchanged"],
        "rag_failed": rag_counts["failed"],
        "rag_failed_match_ids": rag_failed_ids,
        "errors": errors,
    }


def run_sync(
    dry_run: bool = False,
    triggered_by: str = "cron",
    sync_rag: bool = True,
) -> Dict[str, Any]:
    """
    Run the full Cricsheet IPL synchronization cycle:
    download archive -> scan JSONs -> compare against sync_files ->
    import new/changed into SQL -> validate scorecards ->
    incrementally ingest match summaries into pgvector RAG.

    A RAG failure never rolls back or deletes successfully committed SQL matches;
    instead it is recorded in `sync_history` for later retry.
    """
    if triggered_by not in VALID_TRIGGERS:
        raise ValueError(
            f"Invalid triggered_by '{triggered_by}'. "
            f"Must be one of: {', '.join(sorted(VALID_TRIGGERS))}."
        )

    sync_id: Optional[int] = None
    if not dry_run:
        sync_id = _insert_sync_history(triggered_by)

    files_checked = 0
    files_downloaded = 0
    matches_inserted = 0
    matches_updated = 0
    matches_skipped = 0
    matches_failed = 0
    validation_passed = 0
    validation_failed = 0
    changed_match_ids: List[int] = []
    rag_counts = {"ingested": 0, "updated": 0, "unchanged": 0, "failed": 0}
    rag_failed_match_ids: List[int] = []
    errors: List[Dict[str, Any]] = []

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "ipl_json.zip"

            logger.info("Downloading Cricsheet IPL archive...")
            download_ipl_archive(archive_path)

            logger.info("Scanning Cricsheet IPL archive...")
            scan_result = scan_ipl_archive(archive_path)

            archive_matches = scan_result["matches"]
            rejected = scan_result["rejected"]
            files_checked = len(archive_matches) + len(rejected)

            if rejected:
                logger.warning("Rejected %d archive file(s).", len(rejected))
                for item in rejected:
                    errors.append({"stage": "scan", **item})

            plan = create_sync_plan(archive_matches)
            to_process = plan["new"] + plan["changed"]
            matches_skipped = len(plan["unchanged"])
            files_downloaded = len(archive_matches)

            if dry_run:
                return {
                    "sync_id": None,
                    "dry_run": True,
                    "status": "dry_run",
                    "files_checked": files_checked,
                    "new_matches": len(plan["new"]),
                    "changed_matches": len(plan["changed"]),
                    "unchanged_matches": len(plan["unchanged"]),
                    "rejected_files": len(rejected),
                }

            raw_by_id = {m["match_id"]: m for m in archive_matches}

            for item in to_process:
                match_id = item["match_id"]
                entry = raw_by_id[match_id]
                match_file = temp_path / entry["filename"]
                match_file.write_bytes(entry["raw_bytes"])

                try:
                    outcome = import_match(match_file, update_existing=True)
                    result_status = outcome["status"]
                    if result_status == "imported":
                        matches_inserted += 1
                        changed_match_ids.append(match_id)
                    elif result_status == "updated":
                        matches_updated += 1
                        changed_match_ids.append(match_id)
                    else:
                        matches_skipped += 1
                        continue

                    try:
                        val = validate_imported_match(match_id)
                        if val["is_valid"]:
                            validation_passed += 1
                        else:
                            validation_failed += 1
                            errors.append(
                                {
                                    "stage": "validation",
                                    "match_id": match_id,
                                    "invalid_innings": val["invalid_innings"],
                                    "details": val["results"],
                                }
                            )
                    except Exception as val_exc:
                        validation_failed += 1
                        logger.error("Scorecard validation failed for match %s: %s", match_id, val_exc)
                        errors.append(
                            {
                                "stage": "validation",
                                "match_id": match_id,
                                "error": str(val_exc),
                            }
                        )
                except Exception as exc:
                    matches_failed += 1
                    logger.error(
                        "Failed syncing match %s: %s",
                        match_id,
                        exc,
                    )
                    errors.append(
                        {
                            "stage": "import",
                            "match_id": match_id,
                            "filename": entry["filename"],
                            "error": str(exc),
                        }
                    )

            # Deduplicate changed match IDs cleanly before incremental RAG ingestion.
            changed_match_ids = list(dict.fromkeys(changed_match_ids))

            if sync_rag and changed_match_ids:
                logger.info(
                    "Running incremental RAG summary ingestion for %d changed match(es)...",
                    len(changed_match_ids),
                )
                try:
                    rag_result = ingest_db_match_summaries(match_ids=changed_match_ids)
                    rag_counts = rag_result["counts"]
                    rag_failed_match_ids = rag_result.get("failed_match_ids", [])
                    for rag_err in rag_result.get("errors", []):
                        errors.append({"stage": "rag", **rag_err})
                except Exception as rag_exc:
                    # Do NOT roll back committed SQL matches; record RAG failure for later retry.
                    logger.error(
                        "Incremental RAG ingestion failed after SQL sync (%d matches): %s",
                        len(changed_match_ids),
                        rag_exc,
                    )
                    rag_counts["failed"] = len(changed_match_ids)
                    rag_failed_match_ids = list(changed_match_ids)
                    errors.append(
                        {
                            "stage": "rag",
                            "match_ids": list(changed_match_ids),
                            "error": str(rag_exc),
                        }
                    )

            if matches_failed > 0 and (matches_inserted + matches_updated) == 0 and to_process:
                final_status = "failed"
            elif (
                matches_failed > 0
                or rejected
                or validation_failed > 0
                or rag_counts["failed"] > 0
                or rag_failed_match_ids
            ):
                final_status = "partial_failure"
            else:
                final_status = "success"

            _update_sync_history(
                sync_id=sync_id,
                status=final_status,
                files_checked=files_checked,
                files_downloaded=files_downloaded,
                matches_inserted=matches_inserted,
                matches_updated=matches_updated,
                matches_skipped=matches_skipped,
                matches_failed=matches_failed,
                error_details=errors if errors else None,
            )

            return {
                "sync_id": sync_id,
                "dry_run": False,
                "status": final_status,
                "files_checked": files_checked,
                "files_downloaded": files_downloaded,
                "matches_inserted": matches_inserted,
                "matches_updated": matches_updated,
                "matches_skipped": matches_skipped,
                "matches_failed": matches_failed,
                "validation_passed": validation_passed,
                "validation_failed": validation_failed,
                "changed_match_ids": changed_match_ids,
                "rag_ingested": rag_counts["ingested"],
                "rag_updated": rag_counts["updated"],
                "rag_unchanged": rag_counts["unchanged"],
                "rag_failed": rag_counts["failed"],
                "rag_failed_match_ids": rag_failed_match_ids,
                "errors": errors,
            }

    except Exception as exc:
        logger.exception("Cricsheet sync failed: %s", exc)
        if sync_id is not None:
            try:
                _update_sync_history(
                    sync_id=sync_id,
                    status="failed",
                    files_checked=files_checked,
                    files_downloaded=files_downloaded,
                    matches_inserted=matches_inserted,
                    matches_updated=matches_updated,
                    matches_skipped=matches_skipped,
                    matches_failed=matches_failed,
                    error_details={"fatal_error": str(exc), "errors": errors},
                )
            except Exception as db_exc:
                logger.error("Could not update sync_history failure row: %s", db_exc)
        raise
