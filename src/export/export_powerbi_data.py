"""Export a privacy-safe, Power BI-ready data model.

Row-level data is never exported. Instead the cleaned dataset is aggregated
into a small "cube" (one row per combination of date, hour, platform, status,
source, stage, SDK version and duration band) with counts and duration totals.
Power BI can slice and total this freely, yet it contains **no transaction
identifiers**.

Tables written (CSV, UTF-8)
---------------------------
fact_onboarding   aggregated counts            (the only large table)
dim_date          calendar for the data period
dim_status        status -> label, outcome group, flags
dim_platform      platform -> label
dim_stage         stage -> display order
dataset_overlap   (optional) ID-overlap percentages between extracts

    python -m src.export.export_powerbi_data --source synthetic
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.analyze_onboarding_funnel import (
    OPTIONAL_COLUMNS,
    OUTCOME_GROUPS,
    OUTCOME_ORDER,
    load_onboarding_data,
)
from src.analysis.onboarding_behaviour import (
    WEEKDAY_NAMES,
    enrich_onboarding_data,
)
from src.config import PROCESSED_DIR, SYNTHETIC_ONBOARDING_FILE

DURATION_BINS = [0, 30, 60, 120, 300, 600, np.inf]
DURATION_LABELS = [
    "1. under 30 sec",
    "2. 30-60 sec",
    "3. 1-2 min",
    "4. 2-5 min",
    "5. 5-10 min",
    "6. over 10 min",
]
NO_DURATION = "0. no duration recorded"

STATUS_LABELS = {
    "auto_approved": "Auto-approved",
    "manually_approved": "Manually approved",
    "auto_declined": "Auto-declined",
    "manually_declined": "Manually declined",
    "user_cancelled": "Cancelled by user",
    "started": "Started, no completion recorded",
    "error": "Error",
    "needs_review": "Needs review",
}

PLATFORM_LABELS = {
    "android": "Android",
    "ios": "iOS",
    "windows": "Windows",
    "macos": "macOS",
    "web": "Web",
    "unknown": "Unknown",
    "missing": "Not recorded",
}

KNOWN_PLATFORMS = {"android", "ios", "windows", "macos"}

STAGE_ORDER = [
    "Country selection",
    "Location check",
    "Data-entry form",
    "Document verification",
    "ID card capture",
    "Selfie capture",
    "Face match",
    "Other",
    "No stage recorded",
]

FACT_KEYS = [
    "created_date",
    "created_hour",
    "platform",
    "status",
    "source",
    "stage",
    "sdk_version",
    "duration_band",
]


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def build_fact_table(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the cleaned data to the cube grain."""

    frame = pd.DataFrame({
        "transaction_id": df["transaction_id"],
        "created_date": df.get("created_date"),
        "created_hour": df.get("created_hour"),
        "platform": df["platform_normalized"],
        "status": df["status"],
        "source": df["source"],
        "stage": df.get("stage"),
        "sdk_version": df.get("sdk_version"),
        "time_spent_seconds": df.get("time_spent_seconds"),
    })

    band = pd.cut(
        frame["time_spent_seconds"],
        bins=DURATION_BINS,
        labels=DURATION_LABELS,
        right=False,
    ).astype("string")

    frame["duration_band"] = band.fillna(NO_DURATION)
    frame["created_date"] = frame["created_date"].fillna("unknown")
    frame["created_hour"] = frame["created_hour"].fillna(-1).astype(int)
    frame["stage"] = frame["stage"].fillna("No stage recorded")
    frame["sdk_version"] = frame["sdk_version"].fillna("missing")

    fact = (
        frame.groupby(FACT_KEYS, dropna=False)
        .agg(
            transactions=("transaction_id", "size"),
            time_spent_sum_seconds=("time_spent_seconds", "sum"),
            time_spent_count=("time_spent_seconds", "count"),
        )
        .reset_index()
    )

    fact["time_spent_sum_seconds"] = fact["time_spent_sum_seconds"].round(1)

    return fact


def build_dim_date(fact: pd.DataFrame) -> pd.DataFrame:
    valid = pd.to_datetime(
        fact.loc[fact["created_date"] != "unknown", "created_date"]
    )

    calendar = pd.DataFrame({
        "date": pd.date_range(valid.min(), valid.max(), freq="D")
    })

    calendar["weekday"] = calendar["date"].dt.day_of_week.map(
        dict(enumerate(WEEKDAY_NAMES))
    )
    calendar["weekday_number"] = calendar["date"].dt.day_of_week + 1
    calendar["day_of_month"] = calendar["date"].dt.day
    calendar["week_start"] = (
        calendar["date"] - pd.to_timedelta(calendar["date"].dt.day_of_week, "D")
    )
    calendar["is_weekend"] = (calendar["weekday_number"] >= 6).astype(int)

    for column in ("date", "week_start"):
        calendar[column] = calendar[column].dt.strftime("%Y-%m-%d")

    return calendar


def build_dim_status() -> pd.DataFrame:
    rows = []

    for status, label in STATUS_LABELS.items():
        group = OUTCOME_GROUPS[status]
        rows.append({
            "status": status,
            "status_label": label,
            "outcome_group": group,
            "outcome_order": OUTCOME_ORDER.index(group) + 1,
            "is_approved": int(group == "Approved"),
            "is_declined": int(group == "Declined"),
            "is_manual": int(status.startswith("manually")),
        })

    return pd.DataFrame(rows)


def build_dim_platform(fact: pd.DataFrame) -> pd.DataFrame:
    platforms = sorted(fact["platform"].unique())

    return pd.DataFrame({
        "platform": platforms,
        "platform_label": [
            PLATFORM_LABELS.get(p, p.title()) for p in platforms
        ],
        "is_known_platform": [int(p in KNOWN_PLATFORMS) for p in platforms],
    })


def build_dim_stage(fact: pd.DataFrame) -> pd.DataFrame:
    stages = list(fact["stage"].unique())

    def order(stage: str) -> int:
        return (
            STAGE_ORDER.index(stage) + 1
            if stage in STAGE_ORDER
            else len(STAGE_ORDER) + 1
        )

    return (
        pd.DataFrame({"stage": stages, "stage_order": [order(s) for s in stages]})
        .sort_values("stage_order")
        .reset_index(drop=True)
    )


def build_dataset_overlap(
    overlap: pd.DataFrame, names: dict[str, str] | None
) -> pd.DataFrame:
    """Long-form overlap table with BOTH directions of every pair.

    ``pct_of_row_ids_in_column`` answers: "what share of the row dataset's
    unique IDs also appear in the column dataset?" - ready for a matrix
    visual with rows = row_dataset and columns = column_dataset.
    """

    names = names or {}
    rows = []

    for _, pair in overlap.iterrows():
        a, b = pair["dataset_a"], pair["dataset_b"]

        for row_name, col_name, row_unique, pct in (
            (a, b, pair["unique_ids_a"], pair["overlap_pct_of_a"]),
            (b, a, pair["unique_ids_b"], pair["overlap_pct_of_b"]),
        ):
            rows.append({
                "row_dataset": names.get(row_name, row_name),
                "column_dataset": names.get(col_name, col_name),
                "row_dataset_unique_ids": int(row_unique),
                "shared_ids": int(pair["overlapping_transaction_ids"]),
                "pct_of_row_ids_in_column": float(pct),
                "jaccard_similarity_pct": float(
                    pair["jaccard_similarity_pct"]
                ),
            })

    return pd.DataFrame(rows)


def verify_export(fact: pd.DataFrame, df: pd.DataFrame) -> None:
    """The cube must reproduce the source totals exactly."""

    assert int(fact["transactions"].sum()) == len(df), "Row total differs"

    cube_status = fact.groupby("status")["transactions"].sum().to_dict()
    source_status = df["status"].value_counts().to_dict()
    assert cube_status == source_status, "Status totals differ"

    assert not any(
        "transaction_id" in column for column in fact.columns
    ), "Identifier column leaked into export"


# --------------------------------------------------------------------------- #
def export_powerbi_data(
    df: pd.DataFrame,
    output_dir: Path,
    overlap: pd.DataFrame | None = None,
    names: dict[str, str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Write all Power BI tables to ``output_dir`` and return them."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fact = build_fact_table(df)
    verify_export(fact, df)

    tables = {
        "fact_onboarding": fact,
        "dim_date": build_dim_date(fact),
        "dim_status": build_dim_status(),
        "dim_platform": build_dim_platform(fact),
        "dim_stage": build_dim_stage(fact),
    }

    if overlap is not None and not overlap.empty:
        tables["dataset_overlap"] = build_dataset_overlap(overlap, names)

    for name, table in tables.items():
        table.to_csv(output_dir / f"{name}.csv", index=False)
        print(f"  wrote {name}.csv ({len(table):,} rows)")

    print("  [verified] cube totals equal source totals; no identifiers")

    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["real", "synthetic"],
                        default="synthetic")
    args = parser.parse_args()

    synthetic = args.source == "synthetic"
    path = SYNTHETIC_ONBOARDING_FILE if synthetic else None
    out = PROCESSED_DIR / ("synthetic" if synthetic else "") / "powerbi"

    data = load_onboarding_data(path=path, extra_columns=OPTIONAL_COLUMNS)
    export_powerbi_data(enrich_onboarding_data(data), out)
