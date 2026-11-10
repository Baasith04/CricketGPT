"""Tests for the Cricsheet automatic sync runner."""

from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.sync.sync_runner import run_sync


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


@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_dry_run_makes_no_writes(
    mock_download, mock_scan, mock_plan, mock_import
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


@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=42)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_imports_new_and_updates_changed(
    mock_download, mock_scan, mock_plan, mock_import, mock_insert_hist, mock_update_hist
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

    summary = run_sync(dry_run=False, triggered_by="cron")

    mock_insert_hist.assert_called_once_with("cron")
    assert summary["sync_id"] == 42
    assert summary["status"] == "success"
    assert summary["matches_inserted"] == 1
    assert summary["matches_updated"] == 1
    assert summary["matches_skipped"] == 1
    assert summary["matches_failed"] == 0
    assert mock_import.call_count == 2
    mock_update_hist.assert_called_once()
    assert mock_update_hist.call_args.kwargs["status"] == "success"


@patch("app.ingestion.sync.sync_runner._update_sync_history")
@patch("app.ingestion.sync.sync_runner._insert_sync_history", return_value=43)
@patch("app.ingestion.sync.sync_runner.import_match")
@patch("app.ingestion.sync.sync_runner.create_sync_plan")
@patch("app.ingestion.sync.sync_runner.scan_ipl_archive")
@patch("app.ingestion.sync.sync_runner.download_ipl_archive")
def test_run_sync_handles_partial_failure(
    mock_download, mock_scan, mock_plan, mock_import, mock_insert_hist, mock_update_hist
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

    summary = run_sync(dry_run=False, triggered_by="cron")

    assert summary["status"] == "partial_failure"
    assert summary["matches_inserted"] == 1
    assert summary["matches_failed"] == 1
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["match_id"] == 100002
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

