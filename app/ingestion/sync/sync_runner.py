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


def run_sync(
    dry_run: bool = False,
    triggered_by: str = "cron",
) -> Dict[str, Any]:
    """
    Run the full Cricsheet IPL synchronization cycle:
    download archive -> scan JSONs -> compare against sync_files -> import new/changed.

    Args:
        dry_run: If True, inspect and classify without writing to the database.
        triggered_by: One of 'cron', 'manual', or 'initial_import'.

    Returns:
        Summary dictionary with sync_id (None for dry_run), status, and match counts.
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
                    elif result_status == "updated":
                        matches_updated += 1
                    else:
                        matches_skipped += 1
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

            if matches_failed > 0 and (matches_inserted + matches_updated) == 0 and to_process:
                final_status = "failed"
            elif matches_failed > 0 or rejected:
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

