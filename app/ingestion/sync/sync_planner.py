
from app.database.connection import get_db_connection


def classify_matches(archive_matches, existing_records):
    """
    Compare archive metadata with previously synchronized records.

    A match is:
    - new: not present in sync_files
    - changed: hash or Cricsheet revision differs
    - unchanged: hash and revision both match

    This function does not write to the database.
    """
    existing_by_id = {}

    for record in existing_records:
        match_id = record["match_id"]

        if match_id in existing_by_id:
            raise ValueError(
                f"Duplicate existing match ID: {match_id}"
            )

        existing_by_id[match_id] = record

    seen_ids = set()
    plan = {
        "new": [],
        "changed": [],
        "unchanged": [],
    }

    for match in archive_matches:
        match_id = match.get("match_id")
        sha256 = match.get("sha256")
        revision = match.get("cricsheet_revision")

        if (
            isinstance(match_id, bool)
            or not isinstance(match_id, int)
            or match_id <= 0
        ):
            raise ValueError("Invalid archive match ID.")

        if match_id in seen_ids:
            raise ValueError(
                f"Duplicate archive match ID: {match_id}"
            )

        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(c not in "0123456789abcdef" for c in sha256)
        ):
            raise ValueError(
                f"Invalid SHA-256 for match {match_id}."
            )

        if (
            isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 1
        ):
            raise ValueError(
                f"Invalid revision for match {match_id}."
            )

        seen_ids.add(match_id)

        item = {
            "match_id": match_id,
            "filename": match.get("filename"),
            "sha256": sha256,
            "cricsheet_revision": revision,
        }

        existing = existing_by_id.get(match_id)

        if existing is None:
            plan["new"].append(item)

        elif (
            existing["sha256"] != sha256
            or existing["cricsheet_revision"] != revision
        ):
            plan["changed"].append(item)

        else:
            plan["unchanged"].append(item)

    return plan



def get_existing_sync_records():
    """
    Read previously synchronized match hashes from Supabase.
    No database modifications are performed.
    """
    query = """
        SELECT
            match_id,
            file_sha256 AS sha256,
            cricsheet_revision
        FROM sync_files
    """

    records = []

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    for row in rows:
        records.append({
            "match_id": row[0],
            "sha256": row[1],
            "cricsheet_revision": row[2],
        })

    return records



def create_sync_plan(archive_matches):
    """
    Read current database records and compare them with the archive.
    """
    existing_records = get_existing_sync_records()

    return classify_matches(
        archive_matches,
        existing_records,
    )
