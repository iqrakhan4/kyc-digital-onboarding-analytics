"""Validate relationships between the unmatched-ID groups.

Prints aggregate statistics only.

    python -m src.analysis.validate_reconciliation_relationships
"""

import pandas as pd

from src.config import dataset_file, load_manifest

DATASETS = {
    "api": "feb_api_events",
    "missing": "feb_missing_events",
    "doc": "feb_doc_verification_events",
    "march": "march_onboarding",
}

_MANIFEST = None


def _path(name):
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = load_manifest()
    return dataset_file(_MANIFEST, DATASETS[name])


def load_ids(name):
    df = pd.read_csv(
        _path(name),
        usecols=["transaction_id"],
        dtype={"transaction_id": "string"},
        low_memory=False,
    )
    return set(
        df["transaction_id"]
        .dropna()
        .str.strip()
        .loc[lambda s: s.ne("")]
        .unique()
    )


def load_cross_period_data():
    doc = pd.read_csv(
        _path("doc"),
        usecols=["transaction_id", "event_time"],
        dtype={"transaction_id": "string"},
        low_memory=False,
    )

    march = pd.read_csv(
        _path("march"),
        usecols=["transaction_id", "created_at", "event_time"],
        dtype={"transaction_id": "string"},
        low_memory=False,
    )

    for df in [doc, march]:
        df["transaction_id"] = df["transaction_id"].str.strip()

    for col in ["event_time"]:
        doc[col] = pd.to_datetime(
            doc[col], errors="coerce", utc=True, format="mixed"
        )

    for col in ["created_at", "event_time"]:
        march[col] = pd.to_datetime(
            march[col], errors="coerce", utc=True, format="mixed"
        )

    return doc, march


def main():
    print("=" * 65)
    print("RECONCILIATION RELATIONSHIP VALIDATION")
    print("=" * 65)

    api_ids = load_ids("api")
    missing_ids = load_ids("missing")
    doc_ids = load_ids("doc")

    api_not_doc = api_ids - doc_ids
    missing_not_api = missing_ids - api_ids

    shared = api_not_doc & missing_not_api

    print("\n1. COMPARING THE TWO UNMATCHED GROUPS")
    print("-" * 45)
    print("API absent from doc-verification:", len(api_not_doc))
    print("Missing absent from API:", len(missing_not_api))
    print("IDs shared by both groups:", len(shared))
    print("Only in API absent from doc-verification:", len(api_not_doc - missing_not_api))
    print("Only in Missing absent from API:", len(missing_not_api - api_not_doc))

    union = api_not_doc | missing_not_api
    jaccard = len(shared) / len(union) if union else 0

    print(f"Jaccard similarity: {jaccard:.4f}")

    if api_not_doc == missing_not_api:
        print("RESULT: Both unmatched groups contain exactly the same IDs.")
    else:
        print("RESULT: The unmatched groups are different.")

    print("\n2. CROSS-PERIOD DATE COMPARISON")
    print("-" * 45)

    doc, march = load_cross_period_data()

    march_ids = set(
        march["transaction_id"].dropna().loc[
            lambda s: s.ne("")
        ].unique()
    )

    cross_ids = doc_ids & march_ids

    doc_match = doc[doc["transaction_id"].isin(cross_ids)]
    march_match = march[march["transaction_id"].isin(cross_ids)]

    doc_dates = (
        doc_match.groupby("transaction_id")["event_time"]
        .min()
        .rename("doc_first_event")
    )

    march_dates = (
        march_match.groupby("transaction_id")
        .agg(
            march_first_event=("event_time", "min"),
            march_created_at=("created_at", "min"),
        )
    )

    comparison = pd.concat([doc_dates, march_dates], axis=1).dropna()

    print("Cross-period unique IDs:", len(cross_ids))
    print("IDs with comparable timestamps:", len(comparison))

    if not comparison.empty:
        comparison["created_minus_doc_days"] = (
            comparison["march_created_at"]
            - comparison["doc_first_event"]
        ).dt.total_seconds() / 86400

        delta = comparison["created_minus_doc_days"]

        print("\nMarch created_at minus February document-verification first event:")
        print(f"Minimum days: {delta.min():.2f}")
        print(f"Median days: {delta.median():.2f}")
        print(f"Maximum days: {delta.max():.2f}")
        print("March created_at later:", int((delta > 0).sum()))
        print("Same timestamp:", int((delta == 0).sum()))
        print("March created_at earlier:", int((delta < 0).sum()))

    print("\n" + "=" * 65)
    print("VALIDATION COMPLETED")
    print("Only aggregate statistics were displayed.")
    print("=" * 65)


if __name__ == "__main__":
    main()