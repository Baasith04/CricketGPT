
import json
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.ingestion.importer import import_match

DATA_DIR = Path(r"C:\Users\CFRSI 4\Downloads\ipl_json")
MAX_WORKERS = 10


def process_match(file_path):
    try:
        result = import_match(
            file_path,
            update_existing=True
        )

        return {
            "success": True,
            "file": file_path.name,
            "match_id": result["match_id"],
            "status": result["status"],
        }

    except Exception as exc:
        return {
            "success": False,
            "file": file_path.name,
            "error": str(exc),
        }


def main():
    files = sorted(DATA_DIR.glob("*.json"))[875:]

    if not files:
        print("No JSON files found.")
        return

    counts = Counter()
    failures = []

    print(f"Total matches: {len(files)}")
    print(f"Parallel workers: {MAX_WORKERS}")
    print("Starting parallel import...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_match, file_path): file_path
            for file_path in files
        }

        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()

            if result["success"]:
                counts[result["status"]] += 1
                print(
                    f"[{index}/{len(files)}] "
                    f"{result['match_id']}: {result['status']}"
                )
            else:
                counts["failed"] += 1
                failures.append(result)

                print(
                    f"[{index}/{len(files)}] "
                    f"FAILED: {result['file']} - {result['error']}"
                )

    report = {
        "total_files": len(files),
        "counts": dict(counts),
        "failures": failures,
    }

    Path("bulk_import_report.json").write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    print("\n========== IMPORT SUMMARY ==========")
    print(f"Imported: {counts['imported']}")
    print(f"Updated: {counts['updated']}")
    print(f"Unchanged: {counts['unchanged']}")
    print(f"Failed: {counts['failed']}")
    print("Report saved to bulk_import_report.json")


if __name__ == "__main__":
    main()
