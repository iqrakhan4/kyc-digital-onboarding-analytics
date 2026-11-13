from pathlib import Path

import pandas as pd


RAW_DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")
OUTPUT_FILE = OUTPUT_DIR / "local_data_inventory.csv"


def profile_csv(file_path: Path) -> dict:
    """Generate a metadata-only profile of a CSV file."""

    print(f"\nProfiling: {file_path.name}")

    try:
        df = pd.read_csv(file_path, low_memory=False)

        profile = {
            "file_name": file_path.name,
            "row_count": len(df),
            "column_count": len(df.columns),
            "duplicate_rows": int(df.duplicated().sum()),
            "missing_cells": int(df.isna().sum().sum()),
            "columns": ", ".join(df.columns.astype(str)),
        }

        print(f"Rows: {profile['row_count']:,}")
        print(f"Columns: {profile['column_count']}")
        print(f"Duplicate rows: {profile['duplicate_rows']:,}")
        print(f"Missing cells: {profile['missing_cells']:,}")

        return profile

    except Exception as error:
        print(f"Could not profile {file_path.name}: {error}")

        return {
            "file_name": file_path.name,
            "error": str(error),
        }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(RAW_DATA_DIR.glob("*.csv"))

    if not csv_files:
        print("No CSV files found in data/raw/")
        print("Add your approved local CSV extracts and try again.")
        return

    print(f"Found {len(csv_files)} CSV files.")

    results = [
        profile_csv(file_path)
        for file_path in csv_files
    ]

    inventory = pd.DataFrame(results)

    inventory.to_csv(OUTPUT_FILE, index=False)

    print("\n" + "=" * 45)
    print("DATA INVENTORY COMPLETED")
    print("=" * 45)
    print(f"Files profiled: {len(csv_files)}")
    print(f"Inventory saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()