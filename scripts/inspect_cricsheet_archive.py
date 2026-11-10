
import tempfile

from pathlib import Path

from app.ingestion.sync.cricsheet_client import (
    download_ipl_archive,
    scan_ipl_archive,
)


def main():
    with tempfile.TemporaryDirectory() as temp_dir:

        archive_path = Path(temp_dir) / "ipl_json.zip"

        print("Downloading Cricsheet IPL archive...")

        download_ipl_archive(archive_path)

        print("Scanning JSON files...")

        result = scan_ipl_archive(archive_path)

        matches = result["matches"]
        rejected = result["rejected"]

        print("\n========== ARCHIVE SUMMARY ==========")
        print(f"Valid JSON files: {len(matches)}")
        print(f"Rejected files: {len(rejected)}")

        print("\n========== SAMPLE MATCHES ==========")

        for match in matches[:5]:
            print({
                "match_id": match["match_id"],
                "filename": match["filename"],
                "revision": match["cricsheet_revision"],
                "sha256": match["sha256"],
            })

        if rejected:
            print("\n========== REJECTED FILES ==========")

            for item in rejected[:20]:
                print(item)


if __name__ == "__main__":
    main()
