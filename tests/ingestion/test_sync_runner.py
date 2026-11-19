"""Tests for the Cricsheet automatic SQL + RAG sync runner."""

from unittest.mock import patch

import pytest

from app.ingestion.sync.sync_runner import retry_failed_rag_sync, run_sync


def _archive_entry(match_id: int, sha: str = "a" * 64, rev: int = 1):
    return {
        "match_id": match_id,
        "filename": f"{match_id}.json",
        "sha256": sha,
        "cricsheet_revision": rev,
        "cricsheet_created_date": "2026-01-01",
        "raw_bytes": b'{"meta":{"revision":1}}',
    }


def _plan_item(match_id: int, sha: str = "a" * 64, rev: int = 1):
    return {
        "match_id": match_id,
        "filename": f"{match_id}.json",
        "sha256": sha,
        "cricsheet_revision": rev,
    }


def test_run_sync_invalid_trigger_raises():
    with pytest.raises(ValueError, match="Invalid triggered_by"):
        run_sync(dry_run=True, triggered_by="invalid_source")


@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_dry_run_makes_no_writes(
    mock_download, mock_scan, mock_plan, mock_import, mock_rag
):
    mock_scan.return_value = {
        "matches": [_archive_entry(100001), _archive_entry(100002)],
        "rejected": [],
    }
    mock_plan.return_value = {
        "new": [_plan_item(100001)],
        "changed": [],
        "unchanged": [_plan_item(100002)],
    }

    summary = run_sync(dry_run=True, triggered_by="manual")

    assert summary["dry_run"] is True
    assert summary["status"] == "dry_run"
    assert summary["sync_id"] is None
    assert summary["new_matches"] == 1
    assert summary["unchanged_matches"] == 1
    mock_import.assert_not_called()
    mock_rag.assert_not_called()


@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner.validate_imported_match")
@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=42)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_imports_new_and_updates_changed(
    mock_download,
    mock_scan,
    mock_plan,
    mock_import,
    mock_insert_hist,
    mock_update_hist,
    mock_validate,
    mock_rag,
):
    mock_scan.return_value = {
        "matches": [
            _archive_entry(100001),
            _archive_entry(100002, sha="b" * 64, rev=2),
            _archive_entry(100003),
        ],
        "rejected": [],
    }
    mock_plan.return_value = {
        "new": [_plan_item(100001)],
        "changed": [_plan_item(100002, sha="b" * 64, rev=2)],
        "unchanged": [_plan_item(100003)],
    }
    mock_import.side_effect = [
        {"match_id": 100001, "status": "imported"},
        {"match_id": 100002, "status": "updated"},
    ]
    mock_validate.return_value = {"match_id": 100001, "is_valid": True, "invalid_innings": 0, "results": []}
    mock_rag.return_value = {
        "processed": 2,
        "counts": {"ingested": 1, "updated": 1, "unchanged": 0, "failed": 0},
        "failed_match_ids": [],
        "errors": [],
    }

    summary = run_sync(dry_run=False, triggered_by="cron")

    mock_insert_hist.assert_called_once_with("cron")
    assert summary["sync_id"] == 42
    assert summary["status"] == "success"
    assert summary["matches_inserted"] == 1
    assert summary["matches_updated"] == 1
    assert summary["matches_skipped"] == 1
    assert summary["matches_failed"] == 0
    assert summary["validation_passed"] == 2
    assert summary["changed_match_ids"] == [100001, 100002]
    assert summary["rag_ingested"] == 1
    assert summary["rag_updated"] == 1
    assert mock_import.call_count == 2
    mock_rag.assert_called_once_with(match_ids=[100001, 100002])
    mock_update_hist.assert_called_once()
    assert mock_update_hist.call_args.kwargs["status"] == "success"


@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner.validate_imported_match")
@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=43)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_handles_partial_failure(
    mock_download,
    mock_scan,
    mock_plan,
    mock_import,
    mock_insert_hist,
    mock_update_hist,
    mock_validate,
    mock_rag,
):
    mock_scan.return_value = {
        "matches": [_archive_entry(100001), _archive_entry(100002)],
        "rejected": [],
    }
    mock_plan.return_value = {
        "new": [_plan_item(100001), _plan_item(100002)],
        "changed": [],
        "unchanged": [],
    }
    mock_import.side_effect = [
        {"match_id": 100001, "status": "imported"},
        RuntimeError("Unknown team in match 100002"),
    ]
    mock_validate.return_value = {"match_id": 100001, "is_valid": True, "invalid_innings": 0, "results": []}
    mock_rag.return_value = {
        "processed": 1,
        "counts": {"ingested": 1, "updated": 0, "unchanged": 0, "failed": 0},
        "failed_match_ids": [],
        "errors": [],
    }

    summary = run_sync(dry_run=False, triggered_by="cron")

    assert summary["status"] == "partial_failure"
    assert summary["matches_inserted"] == 1
    assert summary["matches_failed"] == 1
    assert summary["changed_match_ids"] == [100001]
    mock_rag.assert_called_once_with(match_ids=[100001])
    assert any(e["match_id"] == 100002 for e in summary["errors"])
    assert mock_update_hist.call_args.kwargs["status"] == "partial_failure"


@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=44)
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_records_fatal_download_failure(
    mock_download, mock_insert_hist, mock_update_hist
):
    mock_download.side_effect = ConnectionError("Cricsheet unreachable")

    with pytest.raises(ConnectionError, match="Cricsheet unreachable"):
        run_sync(dry_run=False, triggered_by="cron")

    mock_update_hist.assert_called_once()
    assert mock_update_hist.call_args.kwargs["status"] == "failed"


@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=45)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_unchanged_matches_do_not_trigger_rag(
    mock_download, mock_scan, mock_plan, mock_import, mock_insert_hist, mock_update_hist, mock_rag
):
    mock_scan.return_value = {
        "matches": [_archive_entry(100001), _archive_entry(100002)],
        "rejected": [],
    }
    mock_plan.return_value = {
        "new": [],
        "changed": [],
        "unchanged": [_plan_item(100001), _plan_item(100002)],
    }

    summary = run_sync(dry_run=False, triggered_by="cron")

    assert summary["status"] == "success"
    assert summary["matches_skipped"] == 2
    assert summary["changed_match_ids"] == []
    assert summary["rag_ingested"] == 0
    mock_import.assert_not_called()
    mock_rag.assert_not_called()


@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner.validate_imported_match")
@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=46)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_multiple_changed_match_ids_passed_incrementally(
    mock_download, mock_scan, mock_plan, mock_import, mock_insert_hist, mock_update_hist, mock_validate, mock_rag
):
    mock_scan.return_value = {
        "matches": [_archive_entry(200001), _archive_entry(200002), _archive_entry(200003)],
        "rejected": [],
    }
    mock_plan.return_value = {
        "new": [_plan_item(200001), _plan_item(200002)],
        "changed": [_plan_item(200003, sha="c" * 64, rev=2)],
        "unchanged": [],
    }
    mock_import.side_effect = [
        {"match_id": 200001, "status": "imported"},
        {"match_id": 200002, "status": "imported"},
        {"match_id": 200003, "status": "updated"},
    ]
    mock_validate.return_value = {"is_valid": True, "invalid_innings": 0, "results": []}
    mock_rag.return_value = {
        "processed": 3,
        "counts": {"ingested": 2, "updated": 1, "unchanged": 0, "failed": 0},
        "failed_match_ids": [],
        "errors": [],
    }

    summary = run_sync(dry_run=False, triggered_by="manual")

    mock_rag.assert_called_once_with(match_ids=[200001, 200002, 200003])
    assert summary["rag_ingested"] == 2
    assert summary["rag_updated"] == 1
    assert summary["status"] == "success"


@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner.validate_imported_match")
@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=47)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_rag_failure_preserves_sql_import_and_records_partial_failure(
    mock_download, mock_scan, mock_plan, mock_import, mock_insert_hist, mock_update_hist, mock_validate, mock_rag
):
    mock_scan.return_value = {
        "matches": [_archive_entry(300001)],
        "rejected": [],
    }
    mock_plan.return_value = {
        "new": [_plan_item(300001)],
        "changed": [],
        "unchanged": [],
    }
    mock_import.return_value = {"match_id": 300001, "status": "imported"}
    mock_validate.return_value = {"is_valid": True, "invalid_innings": 0, "results": []}
    mock_rag.side_effect = RuntimeError("Gemini quota exhausted")

    summary = run_sync(dry_run=False, triggered_by="cron")

    assert summary["matches_inserted"] == 1
    assert summary["status"] == "partial_failure"
    assert summary["rag_failed"] == 1
    assert summary["rag_failed_match_ids"] == [300001]
    assert any(e["stage"] == "rag" and e["match_ids"] == [300001] for e in summary["errors"])
    assert mock_update_hist.call_args.kwargs["status"] == "partial_failure"


@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=48)
@patch("app.ingestion.sync.sync_runner.ingest_db_match_summaries")
@patch("app.ingestion.sync.sync_runner.get_db_connection")
def test_retry_failed_rag_sync_recovers_failed_match_ids(
    mock_conn, mock_rag, mock_insert_hist, mock_update_hist
):
    cur = mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = (
        47,
        [{"stage": "rag", "match_ids": [300001, 300002], "error": "Transient error"}],
    )
    mock_rag.return_value = {
        "processed": 2,
        "counts": {"ingested": 2, "updated": 0, "unchanged": 0, "failed": 0},
        "failed_match_ids": [],
        "errors": [],
    }

    res = retry_failed_rag_sync(sync_id=47, triggered_by="manual")

    mock_rag.assert_called_once_with(match_ids=[300001, 300002])
    assert res["status"] == "success"
    assert res["retried_match_ids"] == [300001, 300002]
    assert res["rag_ingested"] == 2
    assert res["rag_failed"] == 0
    assert mock_update_hist.call_args.kwargs["status"] == "success"
