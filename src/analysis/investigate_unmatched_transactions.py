"""Investigate transaction IDs that appear in one extract but not another.

Only aggregate statistics are printed; identifiers are never displayed.
Dataset filenames come from the local manifest, never from this file.

    python -m src.analysis.investigate_unmatched_transactions
"""

import pandas as pd

from src.config import PROCESSED_DIR as OUTPUT, dataset_file, load_manifest

# Logical dataset names (defined in config/dataset_manifest.local.json).
DATASETS = {
    "api": "feb_api_events",
    "successful": "feb_successful_transactions",
    "missing": "feb_missing_events",
    "doc": "feb_doc_verification_events",
    "march": "march_onboarding",
}


def load_csv(name, columns):
    manifest = load_manifest()

    return pd.read_csv(
        dataset_file(manifest, DATASETS[name]),
        usecols=columns,
        dtype={"transaction_id": "string"},
        low_memory=False,
    )


def clean_ids(series):
    return set(
        series.dropna().str.strip().loc[lambda s: s.ne("")].unique()
    )


def report_group(label, df, mask, date_columns, category_columns):
    """Print aggregate statistics only; never print transaction IDs."""

    subset = df.loc[mask]

    print(f"\n{label}")
    print(f"Rows: {len(subset):,}")
    print(
        "Unique transaction IDs:",
        subset["transaction_id"].nunique(),
    )

    for column in date_columns:
        if column not in subset.columns:
            continue

        dates = pd.to_datetime(
            subset[column],
            errors="coerce",
            utc=True,
            format="mixed",
        ).dropna()

        if not dates.empty:
            print(
                f"{column}: "
                f"{dates.min()} to {dates.max()}"
            )

    for column in category_columns:
        if column in subset.columns:
            print(f"\n{column} distribution:")
            print(
                subset[column]
                .fillna("Missing")
                .value_counts()
                .head(10)
                .to_string()
            )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    api = load_csv(
        "api",
        ["transaction_id", "event_time", "created_at", "status_code"],
    )

    successful = load_csv(
        "successful",
        ["transaction_id", "created_at", "status", "event_time"],
    )

    missing = load_csv(
        "missing",
        ["transaction_id", "created_at", "event_time", "status_code"],
    )

    doc = load_csv(
        "doc",
        ["transaction_id", "created_at", "event_time", "status_code"],
    )

    march = load_csv(
        "march",
        [
            "transaction_id",
            "created_at",
            "event_time",
            "transaction_start_timestamp",
            "status",
        ],
    )

    api_ids = clean_ids(api["transaction_id"])
    successful_ids = clean_ids(successful["transaction_id"])
    missing_ids = clean_ids(missing["transaction_id"])
    doc_ids = clean_ids(doc["transaction_id"])

    print("=" * 60)
    print("UNMATCHED TRANSACTION INVESTIGATION")
    print("=" * 60)

    # Successful transactions absent from API
    unmatched_success = successful_ids - api_ids

    report_group(
        "SUCCESSFUL TRANSACTIONS ABSENT FROM API",
        successful,
        successful["transaction_id"].isin(unmatched_success),
        ["created_at", "event_time"],
        ["status"],
    )

    # API transactions absent from document-verification events
    api_not_doc = api_ids - doc_ids

    report_group(
        "API TRANSACTIONS ABSENT FROM DOCUMENT-VERIFICATION EVENTS",
        api,
        api["transaction_id"].isin(api_not_doc),
        ["created_at", "event_time"],
        ["status_code"],
    )

    # Missing-event transactions absent from API
    missing_not_api = missing_ids - api_ids

    report_group(
        "MISSING-EVENT TRANSACTIONS ABSENT FROM API",
        missing,
        missing["transaction_id"].isin(missing_not_api),
        ["created_at", "event_time"],
        ["status_code"],
    )

    # March IDs also appearing in February document-verification events
    march_ids = clean_ids(march["transaction_id"])
    cross_period_ids = march_ids.intersection(doc_ids)

    report_group(
        "MARCH TRANSACTIONS ALSO PRESENT IN FEBRUARY DOCUMENT-VERIFICATION EVENTS",
        march,
        march["transaction_id"].isin(cross_period_ids),
        [
            "created_at",
            "event_time",
            "transaction_start_timestamp",
        ],
        ["status"],
    )

    print("\n" + "=" * 60)
    print("INVESTIGATION COMPLETED")
    print("=" * 60)
    print("All results are aggregate statistics.")
    print("No transaction identifiers were exported.")


if __name__ == "__main__":
    main()
