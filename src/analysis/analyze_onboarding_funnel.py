"""Onboarding funnel analysis (outcome, source and platform summaries).

Run from the project root::

    python -m src.analysis.analyze_onboarding_funnel                 # real data
    python -m src.analysis.analyze_onboarding_funnel --source synthetic

Only aggregate summaries are exported; no transaction identifiers are written.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.config import (
    PROCESSED_DIR as OUTPUT_DIR,
    RAW_DIR,
    SYNTHETIC_ONBOARDING_FILE,
)

REQUIRED_COLUMNS = [
    "transaction_id",
    "status",
    "source",
    "platform",
]

# Optional columns used by the behaviour / drop-off analysis.
OPTIONAL_COLUMNS = [
    "created_at",
    "event_time",
    "transaction_start_timestamp",
    "last_executed_module",
    "sdk_version",
    "time_spent",
    "total_transaction_updates",
]

EXPECTED_STATUSES = {
    "auto_approved",
    "started",
    "user_cancelled",
    "manually_approved",
    "auto_declined",
    "manually_declined",
    "error",
    "needs_review",
}

APPROVED_STATUSES = {
    "auto_approved",
    "manually_approved",
}

DECLINED_STATUSES = {
    "auto_declined",
    "manually_declined",
}

# Business-friendly grouping of the eight raw statuses.
OUTCOME_GROUPS = {
    "auto_approved": "Approved",
    "manually_approved": "Approved",
    "auto_declined": "Declined",
    "manually_declined": "Declined",
    "user_cancelled": "Cancelled by user",
    "started": "No completion recorded",
    "error": "Error / needs review",
    "needs_review": "Error / needs review",
}

OUTCOME_ORDER = [
    "Approved",
    "Declined",
    "Cancelled by user",
    "No completion recorded",
    "Error / needs review",
]


def add_outcome_group(df):
    """Return a copy of ``df`` with an ``outcome_group`` column."""

    result = df.copy()
    result["outcome_group"] = result["status"].map(OUTCOME_GROUPS)
    return result


def _locate_onboarding_file():
    """Find the single raw March onboarding extract."""

    matching_files = sorted(
        RAW_DIR.glob("query_result_2026-05-12*.csv")
    )

    if len(matching_files) != 1:
        raise FileNotFoundError(
            "Expected exactly one March onboarding extract. "
            f"Found: {len(matching_files)}"
        )

    return matching_files[0]


def load_onboarding_data(path=None, extra_columns=(), verbose=True):
    """Load and validate the transaction-level onboarding dataset.

    Parameters
    ----------
    path:
        CSV to load. Defaults to the private March extract in ``data/raw``.
    extra_columns:
        Additional columns to load *if present* in the file.
    verbose:
        Print basic load statistics.
    """

    file_path = Path(path) if path else _locate_onboarding_file()

    header = pd.read_csv(file_path, nrows=0).columns

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in header
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    usecols = REQUIRED_COLUMNS + [
        column
        for column in extra_columns
        if column in header and column not in REQUIRED_COLUMNS
    ]

    df = pd.read_csv(
        file_path,
        usecols=usecols,
        low_memory=False,
    )

    if df["transaction_id"].isna().any():
        raise ValueError("Transaction IDs contain missing values.")

    if df["transaction_id"].duplicated().any():
        raise ValueError(
            "Expected one record per transaction, "
            "but duplicate transaction IDs were found."
        )

    if df[["status", "source"]].isna().any().any():
        raise ValueError(
            "Status or source contains missing values."
        )

    observed_statuses = set(df["status"].unique())
    unexpected_statuses = observed_statuses - EXPECTED_STATUSES

    if unexpected_statuses:
        raise ValueError(
            f"Unexpected transaction statuses: {unexpected_statuses}"
        )

    # Normalize platform labels for consistent grouping.
    df["platform_normalized"] = (
        df["platform"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace("", pd.NA)
        .fillna("missing")
    )

    if verbose:
        print(f"Loaded transactions: {len(df):,}")
        print("Unique transaction IDs:", df["transaction_id"].nunique())

    return df


def build_status_summary(df):
    """Calculate overall transaction outcome distribution."""

    summary = (
        df.groupby("status")
        .size()
        .reset_index(name="transactions")
    )

    summary["percentage"] = (
        summary["transactions"] / len(df) * 100
    ).round(2)

    summary = summary.sort_values(
        "transactions",
        ascending=False,
    )

    return summary


def build_source_status_summary(df):
    """Calculate status distribution within each source."""

    summary = (
        df.groupby(["source", "status"])
        .size()
        .reset_index(name="transactions")
    )

    source_totals = (
        df.groupby("source")
        .size()
        .rename("source_total")
    )

    summary = summary.join(
        source_totals,
        on="source",
    )

    summary["percentage_within_source"] = (
        summary["transactions"] / summary["source_total"] * 100
    ).round(2)

    return summary.sort_values(
        ["source", "transactions"],
        ascending=[True, False],
    )


def build_platform_status_summary(df):
    """Calculate status distribution within normalized platforms."""

    summary = (
        df.groupby(["platform_normalized", "status"])
        .size()
        .reset_index(name="transactions")
    )

    platform_totals = (
        df.groupby("platform_normalized")
        .size()
        .rename("platform_total")
    )

    summary = summary.join(
        platform_totals,
        on="platform_normalized",
    )

    summary["percentage_within_platform"] = (
        summary["transactions"] / summary["platform_total"] * 100
    ).round(2)

    return summary.sort_values(
        ["platform_normalized", "transactions"],
        ascending=[True, False],
    )
    
def build_automated_platform_summary(df):
    """Compare automated approval outcomes across known platforms."""

    known_platforms = {
        "android",
        "ios",
        "windows",
        "macos",
    }

    automated_statuses = {
        "auto_approved",
        "auto_declined",
    }

    filtered = df[
        df["platform_normalized"].isin(known_platforms)
        & df["status"].isin(automated_statuses)
    ]

    summary = (
        filtered.groupby("platform_normalized")["status"]
        .value_counts()
        .unstack(fill_value=0)
        .reset_index()
    )

    for status in automated_statuses:
        if status not in summary.columns:
            summary[status] = 0

    summary["decided_transactions"] = (
        summary["auto_approved"] + summary["auto_declined"]
    )

    summary["automated_approval_rate"] = (
        summary["auto_approved"]
        / summary["decided_transactions"]
        * 100
    ).round(2)

    return summary.sort_values(
        "automated_approval_rate",
        ascending=False,
    )

def build_kpi_summary(df):
    """Calculate headline onboarding funnel KPIs."""

    total = len(df)

    approved = int(
        df["status"].isin(APPROVED_STATUSES).sum()
    )

    declined = int(
        df["status"].isin(DECLINED_STATUSES).sum()
    )

    cancelled = int(
        (df["status"] == "user_cancelled").sum()
    )

    started = int(
        (df["status"] == "started").sum()
    )

    errors = int(
        (df["status"] == "error").sum()
    )

    needs_review = int(
        (df["status"] == "needs_review").sum()
    )

    decided = approved + declined

    metrics = [
        ("total_transactions", total, "transactions"),
        ("approved_transactions", approved, "transactions"),
        ("declined_transactions", declined, "transactions"),
        ("cancelled_transactions", cancelled, "transactions"),
        ("started_transactions", started, "transactions"),
        ("error_transactions", errors, "transactions"),
        ("needs_review_transactions", needs_review, "transactions"),
        (
            "approval_share_all_transactions",
            round(approved / total * 100, 2),
            "percent",
        ),
        (
            "approval_rate_among_decided",
            round(approved / decided * 100, 2) if decided else 0,
            "percent",
        ),
        (
            "decline_share_all_transactions",
            round(declined / total * 100, 2),
            "percent",
        ),
        (
            "cancellation_share_all_transactions",
            round(cancelled / total * 100, 2),
            "percent",
        ),
    ]

    return pd.DataFrame(
        metrics,
        columns=["metric", "value", "unit"],
    )

def build_all_summaries(df):
    """Return every funnel summary keyed by its output filename."""

    return {
        "onboarding_status_summary.csv": build_status_summary(df),
        "source_status_summary.csv": build_source_status_summary(df),
        "platform_status_summary.csv": build_platform_status_summary(df),
        "onboarding_kpi_summary.csv": build_kpi_summary(df),
        "automated_platform_summary.csv": (
            build_automated_platform_summary(df)
        ),
    }


def main(source="real", output_dir=None):
    output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("ONBOARDING FUNNEL ANALYSIS")
    print("=" * 70)

    path = SYNTHETIC_ONBOARDING_FILE if source == "synthetic" else None
    df = load_onboarding_data(path=path)

    summaries = build_all_summaries(df)

    print("\n" + "=" * 70)
    print("GENERATED ANALYTICAL SUMMARIES")
    print("=" * 70)

    for filename, summary in summaries.items():
        output_file = output_dir / filename

        summary.to_csv(output_file, index=False)

        print(f"\n{filename}")
        print(summary.to_string(index=False))
        print(f"Saved to: {output_file}")

    print("\nAnalysis completed successfully.")
    print("Only aggregate analytical data was exported.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["real", "synthetic"],
        default="real",
    )
    args = parser.parse_args()

    out = (
        OUTPUT_DIR / "synthetic" if args.source == "synthetic" else None
    )
    main(source=args.source, output_dir=out)
