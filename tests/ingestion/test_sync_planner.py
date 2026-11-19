
import pytest

from app.ingestion.sync.sync_planner import classify_matches


def archive_match(match_id, sha="a" * 64, revision=1):
    return {
        "match_id": match_id,
        "filename": f"{match_id}.json",
        "sha256": sha,
        "cricsheet_revision": revision,
    }


def existing_match(match_id, sha="a" * 64, revision=1):
    return {
        "match_id": match_id,
        "sha256": sha,
        "cricsheet_revision": revision,
    }


def test_new_match():
    plan = classify_matches(
        [archive_match(100001)],
        [],
    )

    assert len(plan["new"]) == 1
    assert plan["new"][0]["match_id"] == 100001


def test_unchanged_match():
    plan = classify_matches(
        [archive_match(100001)],
        [existing_match(100001)],
    )

    assert len(plan["unchanged"]) == 1
    assert plan["new"] == []
    assert plan["changed"] == []


def test_changed_hash():
    plan = classify_matches(
        [archive_match(100001, sha="b" * 64)],
        [existing_match(100001, sha="a" * 64)],
    )

    assert len(plan["changed"]) == 1


def test_changed_revision():
    plan = classify_matches(
        [archive_match(100001, revision=2)],
        [existing_match(100001, revision=1)],
    )

    assert len(plan["changed"]) == 1


def test_multiple_categories():
    archive = [
        archive_match(100001),
        archive_match(100002, sha="b" * 64),
        archive_match(100003),
    ]

    existing = [
        existing_match(100001),
        existing_match(100002, sha="a" * 64),
    ]

    plan = classify_matches(archive, existing)

    assert len(plan["new"]) == 1
    assert len(plan["changed"]) == 1
    assert len(plan["unchanged"]) == 1


def test_duplicate_archive_id_rejected():
    with pytest.raises(ValueError, match="Duplicate archive"):
        classify_matches(
            [
                archive_match(100001),
                archive_match(100001),
            ],
            [],
        )


def test_invalid_hash_rejected():
    with pytest.raises(ValueError, match="Invalid SHA-256"):
        classify_matches(
            [archive_match(100001, sha="invalid")],
            [],
        )


def test_invalid_revision_rejected():
    with pytest.raises(ValueError, match="Invalid revision"):
        classify_matches(
            [archive_match(100001, revision=0)],
            [],
        )


def test_duplicate_existing_id_rejected():
    with pytest.raises(ValueError, match="Duplicate existing"):
        classify_matches(
            [archive_match(100001)],
            [
                existing_match(100001),
                existing_match(100001),
            ],
        )
