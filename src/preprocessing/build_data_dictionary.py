
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed"

CHUNK_SIZE = 100_000


TIMESTAMP_PATTERN = re.compile(
    r"(^@?timestamp$|created_at|event_time|"
    r"transaction_start_timestamp|updated_at|"
    r"started_at|completed_at|_date$)",
    re.IGNORECASE,
)

IDENTIFIER_PATTERN = re.compile(
    r"(^id$|_id$|transaction_id|transactionid|"
    r"application_id|app_id|customer_id|"
    r"request_id|reference_id|module_id|workflow_id)",
    re.IGNORECASE,
)

PAYLOAD_PATTERN = re.compile(
    r"(payload|bodystr|request_body|response_body|"
    r"req\.body|res\.body)",
    re.IGNORECASE,
)

METRIC_PATTERN = re.compile(
    r"(^|[._])(amount|count|duration|time_spent|"
    r"response_?time|latency|score|size|"
    r"attempt(_number)?|retry|"
    r"total_transaction_updates)([._]|$)|"
    r"^responseTime$",
    re.IGNORECASE,
)

STATUS_PATTERN = re.compile(
    r"(status|decision|reason|condition|"
    r"module|platform|country|type|category|"
    r"statuscode)",
    re.IGNORECASE,
)

SENSITIVE_PATTERN = re.compile(
    r"(email|phone|mobile|ip_address|"
    r"address|customer_name|full_name|"
    r"document|aadhaar|pan|dob|"
    r"account_number|token|authorization|"
    r"payload|bodystr|request_body|response_body|"
    r"req\.body|res\.body|"
    r"transaction_id|transactionid|"
    r"application_id|customer_id|"
    r"req\.originalurl|original_url)",
    re.IGNORECASE,
)


def classify_column(column):
    name = str(column).strip()

    if TIMESTAMP_PATTERN.search(name):
        return "timestamp"

    if IDENTIFIER_PATTERN.search(name):
        return "identifier"

    if METRIC_PATTERN.search(name):
        return "metric"

    if PAYLOAD_PATTERN.search(name):
        return "payload_or_api_data"

    if STATUS_PATTERN.search(name):
        return "status_or_category"

    return "other"



def profile_csv(file_path):
    print(f"Profiling: {file_path.name}")

    row_count = 0
    non_null_counts = {}
    inferred_dtypes = {}

    for chunk in pd.read_csv(
        file_path,
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        if not non_null_counts:
            non_null_counts = {
                column: 0 for column in chunk.columns
            }

            inferred_dtypes = {
                column: str(dtype)
                for column, dtype in chunk.dtypes.items()
            }

        row_count += len(chunk)

        for column in chunk.columns:
            non_null_counts[column] += int(
                chunk[column].notna().sum()
            )

    results = []

    for column, non_null_count in non_null_counts.items():
        missing_count = row_count - non_null_count

        results.append({
            "dataset": file_path.name,
            "total_rows": row_count,
            "column_name": column,
            "inferred_dtype": inferred_dtypes[column],
            "non_null_count": non_null_count,
            "missing_count": missing_count,
            "missing_percentage": round(
                missing_count / row_count * 100, 2
            ) if row_count else 0,
            "probable_role": classify_column(column),
            "potentially_sensitive": bool(
            SENSITIVE_PATTERN.search(column)
            or IDENTIFIER_PATTERN.search(column)
        ),
        })

    return results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {RAW_DIR}"
        )

    all_results = []

    print("=" * 65)
    print("TECHNICAL DATA DICTIONARY GENERATION")
    print("=" * 65)
    print(f"CSV files found: {len(csv_files)}")

    for file_path in csv_files:
        try:
            all_results.extend(profile_csv(file_path))
        except Exception as error:
            print(
                f"Could not profile {file_path.name}: {error}"
            )

    if not all_results:
        raise RuntimeError("No dataset metadata was generated.")

    dictionary = pd.DataFrame(all_results)

    output_file = (
        OUTPUT_DIR / "data_dictionary_technical.csv"
    )

    dictionary.to_csv(output_file, index=False)

    print("\n" + "=" * 65)
    print("DATA DICTIONARY SUMMARY")
    print("=" * 65)

    print("Datasets profiled:", dictionary["dataset"].nunique())
    print("Total columns profiled:", len(dictionary))

    print("\nProbable column roles:")
    print(
        dictionary["probable_role"]
        .value_counts()
        .to_string()
    )

    print("\nPotentially sensitive columns:")
    sensitive = dictionary[
        dictionary["potentially_sensitive"]
    ]

    print("Count:", len(sensitive))
    print("Affected datasets:", sensitive["dataset"].nunique())

    print("\nOutput:", output_file)
    print("Only metadata and aggregate statistics were exported.")


if __name__ == "__main__":
    main()
