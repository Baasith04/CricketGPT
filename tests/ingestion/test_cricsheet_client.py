
import json
import zipfile

import pytest

from app.ingestion.sync.cricsheet_client import (
    calculate_sha256,
    scan_ipl_archive,
)


def create_test_archive(tmp_path, files):
    archive_path = tmp_path / "test_ipl.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)

    return archive_path


def test_calculate_sha256():
    result = calculate_sha256(b"cricket")

    assert len(result) == 64


def test_scan_valid_match(tmp_path):
    data = {
        "meta": {
            "revision": 1,
            "created": "2026-01-01",
        },
        "info": {},
        "innings": [],
    }

    archive_path = create_test_archive(
        tmp_path,
        {
            "335982.json": json.dumps(data),
        },
    )

    result = scan_ipl_archive(archive_path)

    assert len(result["matches"]) == 1
    assert result["matches"][0]["match_id"] == 335982
    assert result["matches"][0]["cricsheet_revision"] == 1
    assert result["rejected"] == []


def test_scan_rejects_invalid_json(tmp_path):
    archive_path = create_test_archive(
        tmp_path,
        {
            "123456.json": "{invalid json",
        },
    )

    result = scan_ipl_archive(archive_path)

    assert result["matches"] == []
    assert len(result["rejected"]) == 1


def test_scan_rejects_missing_revision(tmp_path):
    data = {
        "meta": {
            "created": "2026-01-01",
        },
    }

    archive_path = create_test_archive(
        tmp_path,
        {
            "123456.json": json.dumps(data),
        },
    )

    result = scan_ipl_archive(archive_path)

    assert result["matches"] == []
    assert len(result["rejected"]) == 1


def test_scan_ignores_non_json_files(tmp_path):
    archive_path = create_test_archive(
        tmp_path,
        {
            "README.txt": "Cricsheet data",
        },
    )

    result = scan_ipl_archive(archive_path)

    assert result["matches"] == []
    assert result["rejected"] == []


def test_scan_rejects_duplicate_match_ids(tmp_path):
    data = {
        "meta": {
            "revision": 1,
            "created": "2026-01-01",
        },
    }

    archive_path = create_test_archive(
        tmp_path,
        {
            "335982.json": json.dumps(data),
            "folder/335982.json": json.dumps(data),
        },
    )

    result = scan_ipl_archive(archive_path)

    assert len(result["matches"]) == 1
    assert len(result["rejected"]) == 1
