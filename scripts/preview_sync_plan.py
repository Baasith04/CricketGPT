
import tempfile

from pathlib import Path

from app.ingestion.sync.cricsheet_client import (
    download_ipl_archive,
    scan_ipl_archive,
)

from app.ingestion.sync.sync_planner import (
    create_sync_plan,
)


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "ipl_json.zip"

        print("Downloading Cricsheet IPL archive...")
        download_ipl_archive(archive_path)

        print("Scanning archive...")
        scan_result = scan_ipl_archive(archive_path)

        if scan_result["rejected"]:
            print(
                f"Rejected files: {len(scan_result['rejected'])}"
            )
            print("Fix archive validation issues before comparison.")
            return

        print("Reading existing Supabase sync records...")
        plan = create_sync_plan(scan_result["matches"])

        print("\n========== SYNC PLAN ==========")

        for category in ("new", "changed", "unchanged"):
            items = plan[category]
            print(f"{category.upper()}: {len(items)}")

            for item in items[:5]:
                print(
                    f"  Match {item['match_id']} | "
                    f"Revision {item['cricsheet_revision']}"
                )

        print("\nNo database records were modified.")


if __name__ == "__main__":
    main()
