
from pathlib import Path
from app.ingestion.parser import parse_match

DATASET = Path(r"C:\Users\CFRSI 4\Downloads\ipl_json")


def main():
    files = list(DATASET.glob("*.json"))

    successful = 0
    failed = []

    for file_path in files:
        try:
            match = parse_match(file_path)

            if not match["innings"]:
                raise ValueError("Match contains no innings")

            successful += 1

        except Exception as error:
            failed.append((file_path.name, str(error)))

    print("\n========== BATCH PARSER TEST ==========")
    print("Total files:", len(files))
    print("Successfully parsed:", successful)
    print("Failed:", len(failed))

    if failed:
        print("\nFailures:")
        for filename, error in failed[:20]:
            print(filename, ":", error)

    print("\nBatch test completed.")


if __name__ == "__main__":
    main()
