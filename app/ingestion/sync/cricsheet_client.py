
import hashlib
import json
import shutil
import tempfile
import zipfile

from pathlib import Path
from urllib.request import Request, urlopen


CRICSHEET_IPL_JSON_URL = (
    "https://cricsheet.org/downloads/ipl_json.zip"
)


def download_ipl_archive(destination):
    """
    Download the official IPL JSON archive.

    The download is written to a temporary file first.
    The destination is replaced only after ZIP validation.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    request = Request(
        CRICSHEET_IPL_JSON_URL,
        headers={"User-Agent": "CricketGPT/1.0"},
    )

    temporary_path = destination.with_suffix(
        destination.suffix + ".part"
    )

    try:
        with urlopen(request, timeout=120) as response:
            with open(temporary_path, "wb") as output:
                shutil.copyfileobj(response, output)

        if not zipfile.is_zipfile(temporary_path):
            raise ValueError(
                "Downloaded Cricsheet file is not a valid ZIP archive."
            )

        temporary_path.replace(destination)

        return destination

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def calculate_sha256(content):
    """Calculate SHA-256 for raw file bytes."""
    return hashlib.sha256(content).hexdigest()


def scan_ipl_archive(archive_path):
    """
    Scan the IPL ZIP archive without extracting it.

    Returns:
        {
            "matches": [...],
            "rejected": [...]
        }
    """
    matches = []
    rejected = []
    seen_match_ids = set()

    with zipfile.ZipFile(archive_path, "r") as archive:

        for filename in sorted(archive.namelist()):

            if not filename.lower().endswith(".json"):
                continue

            if filename.endswith("/"):
                continue

            try:
                match_id = int(Path(filename).stem)

                if match_id in seen_match_ids:
                    raise ValueError(
                        f"Duplicate match ID: {match_id}"
                    )

                raw_bytes = archive.read(filename)

                data = json.loads(raw_bytes.decode("utf-8"))

                if not isinstance(data, dict):
                    raise ValueError("JSON root must be an object.")

                meta = data.get("meta")

                if not isinstance(meta, dict):
                    raise ValueError("Missing or invalid meta section.")

                revision = meta.get("revision")

                if (
                    isinstance(revision, bool)
                    or not isinstance(revision, int)
                    or revision < 1
                ):
                    raise ValueError("Invalid Cricsheet revision.")

                created = meta.get("created")

                if not isinstance(created, str):
                    raise ValueError("Missing created date.")

                entry = {
                    "match_id": match_id,
                    "filename": Path(filename).name,
                    "sha256": calculate_sha256(raw_bytes),
                    "cricsheet_revision": revision,
                    "cricsheet_created_date": created,
                    "raw_bytes": raw_bytes,
                }

                matches.append(entry)
                seen_match_ids.add(match_id)

            except Exception as error:
                rejected.append({
                    "filename": filename,
                    "reason": str(error),
                })

    return {
        "matches": matches,
        "rejected": rejected,
    }
