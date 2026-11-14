from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "processed"

FILES = {
    "api": "February API hits.csv",
    "successful": "February successful transactions.csv",
    "missing": "feb missing.csv",
    "digi": "Feb Digi Hits.csv",
    "march": "query_result_2026-05-12T16_00_44.770167981+05_30.csv",
}


def load_csv(name, columns):
    return pd.read_csv(
        RAW / FILES[name],
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

    digi = load_csv(
        "digi",
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
    digi_ids = clean_ids(digi["transaction_id"])

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

    # API transactions absent from Digi Hits
    api_not_digi = api_ids - digi_ids

    report_group(
        "API TRANSACTIONS ABSENT FROM DIGI HITS",
        api,
        api["transaction_id"].isin(api_not_digi),
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

    # March IDs also appearing in February Digi Hits
    march_ids = clean_ids(march["transaction_id"])
    cross_period_ids = march_ids.intersection(digi_ids)

    report_group(
        "MARCH TRANSACTIONS ALSO PRESENT IN FEBRUARY DIGI HITS",
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
