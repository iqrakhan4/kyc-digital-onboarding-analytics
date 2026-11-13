from pathlib import Path
import re

import pandas as pd


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")

COLUMN_REPORT = OUTPUT_DIR / "column_quality_report.csv"
KEY_REPORT = OUTPUT_DIR / "identifier_quality_report.csv"
DATE_REPORT = OUTPUT_DIR / "timestamp_quality_report.csv"

# Column names are used only to identify likely identifiers.
# No actual identifier values are written to the reports.
IDENTIFIER_PATTERN = re.compile(
    r"transaction.?id|request.?id|customer.?id|"
    r"application.?id|journey.?id|user.?id",
    re.IGNORECASE,
)

TIMESTAMP_PATTERN = re.compile(
    r"timestamp|created.?at|event.?time|date|time",
    re.IGNORECASE,
)


def assess_file(file_path):
    print(f"\nAssessing: {file_path.name}")

    try:
        df = pd.read_csv(file_path, low_memory=False)

        row_count = len(df)

        # Full-row duplicates
        duplicate_rows = int(df.duplicated().sum())

        for column in df.columns:
            series = df[column]

            missing_count = int(series.isna().sum())
            distinct_count = int(series.nunique(dropna=True))

            column_results.append({
                "file_name": file_path.name,
                "column_name": column,
                "data_type": str(series.dtype),
                "missing_count": missing_count,
                "missing_percentage": round(
                    missing_count / row_count * 100, 2
                ) if row_count else 0,
                "distinct_values": distinct_count,
                "duplicate_rows_in_file": duplicate_rows,
            })

            # Check likely identifier columns
            if IDENTIFIER_PATTERN.search(str(column)):
                key_results.append({
                    "file_name": file_path.name,
                    "column_name": column,
                    "total_rows": row_count,
                    "non_null_values": int(series.notna().sum()),
                    "unique_values": distinct_count,
                    "repeated_non_null_rows": int(
                        series.notna().sum() - distinct_count
                    ),
                    "missing_values": missing_count,
                })

            # Check likely date/time columns
            if TIMESTAMP_PATTERN.search(str(column)):
                parsed = pd.to_datetime(
                    series,
                    errors="coerce",
                    utc=True,
                )

                invalid_count = int(
                    (series.notna() & parsed.isna()).sum()
                )

                valid = parsed.dropna()

                date_results.append({
                    "file_name": file_path.name,
                    "column_name": column,
                    "non_null_values": int(series.notna().sum()),
                    "valid_timestamps": int(parsed.notna().sum()),
                    "invalid_timestamps": invalid_count,
                    "earliest_timestamp": (
                        valid.min().isoformat() if not valid.empty else None
                    ),
                    "latest_timestamp": (
                        valid.max().isoformat() if not valid.empty else None
                    ),
                })

        print(f"Rows: {row_count:,}")
        print(f"Columns: {len(df.columns)}")
        print(f"Exact duplicate rows: {duplicate_rows:,}")
        print("Column-level checks completed.")

    except Exception as error:
        print(f"ERROR processing {file_path.name}: {error}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(RAW_DIR.glob("*.csv"))

    if not csv_files:
        print("No CSV files found in data/raw/")
        return

    global column_results, key_results, date_results

    column_results = []
    key_results = []
    date_results = []

    print(f"Starting assessment of {len(csv_files)} CSV files.")

    for file_path in csv_files:
        assess_file(file_path)

    pd.DataFrame(column_results).to_csv(
        COLUMN_REPORT, index=False
    )

    pd.DataFrame(key_results).to_csv(
        KEY_REPORT, index=False
    )

    pd.DataFrame(date_results).to_csv(
        DATE_REPORT, index=False
    )

    print("\n" + "=" * 50)
    print("DATA QUALITY ASSESSMENT COMPLETED")
    print("=" * 50)
    print(f"Column report: {COLUMN_REPORT}")
    print(f"Identifier report: {KEY_REPORT}")
    print(f"Timestamp report: {DATE_REPORT}")


if __name__ == "__main__":
    main()
