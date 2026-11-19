
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


def test_download_retries_transient_http_503_and_succeeds(tmp_path):
    import io
    from unittest.mock import patch
    from urllib.error import HTTPError
    from app.ingestion.sync.cricsheet_client import download_ipl_archive

    zip_path = create_test_archive(tmp_path, {"123456.json": '{"meta":{"revision":1}}'})
    valid_zip_bytes = zip_path.read_bytes()
    dest = tmp_path / "downloaded.zip"

    good_resp = io.BytesIO(valid_zip_bytes)
    good_resp.__enter__ = lambda s: s
    good_resp.__exit__ = lambda s, *a: None

    transient_err = HTTPError(
        url="https://cricsheet.org/downloads/ipl_json.zip",
        code=503,
        msg="Service Unavailable",
        hdrs=None,
        fp=None,
    )

    with patch("app.ingestion.sync.cricsheet_client.time.sleep") as mock_sleep, \
         patch("app.ingestion.sync.cricsheet_client.urlopen", side_effect=[transient_err, good_resp]) as mock_open:
        result = download_ipl_archive(dest, max_attempts=3, base_delay=0.1)

    assert result == dest
    assert dest.is_file()
    assert mock_open.call_count == 2
    mock_sleep.assert_called_once_with(0.1)


def test_download_does_not_retry_permanent_http_404(tmp_path):
    from unittest.mock import patch
    from urllib.error import HTTPError
    from app.ingestion.sync.cricsheet_client import download_ipl_archive

    dest = tmp_path / "downloaded_404.zip"
    perm_err = HTTPError(
        url="https://cricsheet.org/downloads/ipl_json.zip",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None,
    )

    with patch("app.ingestion.sync.cricsheet_client.time.sleep") as mock_sleep, \
         patch("app.ingestion.sync.cricsheet_client.urlopen", side_effect=perm_err) as mock_open:
        with pytest.raises(HTTPError):
            download_ipl_archive(dest, max_attempts=3, base_delay=0.1)

    assert mock_open.call_count == 1
    mock_sleep.assert_not_called()
    assert not dest.exists()
    assert not dest.with_suffix(".zip.part").exists()
