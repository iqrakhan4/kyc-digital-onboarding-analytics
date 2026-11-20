"""Stage drop-off, platform, timing and trend analysis.

Builds on the validated transaction-level dataset produced by
``analyze_onboarding_funnel.load_onboarding_data``. Every function here
returns an *aggregate* DataFrame - no transaction identifiers are exposed.

Assumptions (flagged in docs/methodology.md because they are unverified):

* ``time_spent`` is recorded in **milliseconds** (the median completed
  journey of ~3 minutes is plausible; seconds would imply hours).
* Timestamps are shown exactly as recorded; their timezone is unknown.
* ``last_executed_module`` is the last module the journey is known to have
  reached - not necessarily the module the user abandoned on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.analyze_onboarding_funnel import (
    OUTCOME_ORDER,
    add_outcome_group,
)
from src.config import load_stage_mapping

TIMESTAMP_FORMAT = "%b %d, %Y, %I:%M %p"

# Journeys longer than this are treated as session-timing artefacts.
MAX_PLAUSIBLE_SECONDS = 3600

KNOWN_PLATFORMS = ["android", "ios", "windows", "macos"]

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

ENRICHMENT_COLUMNS = [
    "created_at",
    "last_executed_module",
    "sdk_version",
    "time_spent",
    "total_transaction_updates",
]


# --------------------------------------------------------------------------- #
# Cleaning / enrichment
# --------------------------------------------------------------------------- #
def parse_timestamps(series: pd.Series) -> pd.Series:
    """Parse export-style timestamps, falling back to flexible parsing."""

    parsed = pd.to_datetime(
        series,
        format=TIMESTAMP_FORMAT,
        errors="coerce",
    )

    unparsed = parsed.isna() & series.notna()

    if unparsed.any():
        fallback = pd.to_datetime(
            series[unparsed],
            format="mixed",
            errors="coerce",
        )
        parsed = parsed.copy()
        parsed.loc[unparsed] = fallback

    return parsed


def parse_numeric(series: pd.Series) -> pd.Series:
    """Convert numbers that may be formatted with thousands separators."""

    cleaned = series.astype("string").str.replace(",", "", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def classify_stage(module: Any, mapping: dict[str, Any]) -> str:
    """Translate a raw module string into a generic stage label."""

    if pd.isna(module) or str(module).strip() == "":
        return mapping["missing_stage"]

    text = str(module).lower()

    for rule in mapping["rules"]:
        if rule["keyword"].lower() in text:
            return rule["stage"]

    return mapping["default_stage"]


def enrich_onboarding_data(
    df: pd.DataFrame,
    stage_mapping: dict[str, Any] | None = None,
    max_time_seconds: int = MAX_PLAUSIBLE_SECONDS,
) -> pd.DataFrame:
    """Add parsed timestamps, cleaned numerics and stage labels.

    Cleaning actions are recorded as boolean flag columns so they can be
    summarised by :func:`build_cleaning_log`.
    """

    mapping = stage_mapping or load_stage_mapping()
    result = add_outcome_group(df)

    # Timestamps ---------------------------------------------------------
    if "created_at" in result:
        result["created_ts"] = parse_timestamps(result["created_at"])
        result["created_date"] = result["created_ts"].dt.strftime("%Y-%m-%d")
        result["created_hour"] = result["created_ts"].dt.hour
        result["created_weekday"] = result["created_ts"].dt.day_of_week

    # Time spent (assumed milliseconds) --------------------------------
    if "time_spent" in result:
        seconds = parse_numeric(result["time_spent"]) / 1000
        outlier = (seconds > max_time_seconds) | (seconds < 0)

        result["time_spent_outlier"] = outlier.fillna(False)
        result["time_spent_seconds"] = seconds.mask(outlier)

    # Update counts ------------------------------------------------------
    if "total_transaction_updates" in result:
        raw = result["total_transaction_updates"].astype("string")
        result["updates_needed_cleaning"] = raw.str.contains(
            ",", regex=False
        ).fillna(False)
        result["total_transaction_updates"] = parse_numeric(raw)

    # Stage --------------------------------------------------------------
    if "last_executed_module" in result:
        result["stage"] = result["last_executed_module"].map(
            lambda module: classify_stage(module, mapping)
        )

    # SDK ----------------------------------------------------------------
    if "sdk_version" in result:
        result["sdk_version"] = (
            result["sdk_version"].astype("string").str.strip().fillna("missing")
        )

    return result


def build_cleaning_log(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise every cleaning decision applied by the enrichment step."""

    rows = [("rows_processed", len(df), "Rows in the validated extract")]

    if "created_ts" in df:
        rows.append((
            "unparsed_created_at",
            int(df["created_ts"].isna().sum()),
            "Timestamps that could not be parsed",
        ))

    if "time_spent_outlier" in df:
        rows.append((
            "time_spent_outliers_excluded",
            int(df["time_spent_outlier"].sum()),
            f"Journeys longer than {MAX_PLAUSIBLE_SECONDS // 60} minutes "
            "excluded from timing statistics",
        ))
        rows.append((
            "time_spent_missing",
            int(df["time_spent"].isna().sum()),
            "Records without a recorded duration",
        ))

    if "updates_needed_cleaning" in df:
        rows.append((
            "update_counts_with_separator",
            int(df["updates_needed_cleaning"].sum()),
            "Update counts stored with a thousands separator",
        ))

    return pd.DataFrame(
        rows,
        columns=["check", "records", "description"],
    )


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #
def build_stage_dropoff_summary(
    df: pd.DataFrame,
    status: str = "user_cancelled",
) -> pd.DataFrame:
    """Distribution of the last recorded stage for a given status."""

    subset = df[df["status"] == status]

    summary = (
        subset.groupby("stage")
        .size()
        .reset_index(name="transactions")
        .sort_values("transactions", ascending=False)
        .reset_index(drop=True)
    )

    summary["pct_of_status"] = (
        summary["transactions"] / max(len(subset), 1) * 100
    ).round(2)

    summary["pct_of_all_transactions"] = (
        summary["transactions"] / len(df) * 100
    ).round(2)

    return summary


def build_platform_cancellation_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Cancellation and approval rates among *completed-flow* records.

    Only ``finishTransaction`` records are used, because 'started' and
    agent-updated records do not reflect the user journey ending.
    """

    finished = df[df["source"] == "finishTransaction"]

    rows = []

    for platform, group in finished.groupby("platform_normalized"):
        total = len(group)
        cancelled = int((group["status"] == "user_cancelled").sum())
        approved = int((group["status"] == "auto_approved").sum())

        rows.append({
            "platform": platform,
            "finished_transactions": total,
            "cancelled": cancelled,
            "cancellation_rate": round(cancelled / total * 100, 2),
            "auto_approved": approved,
            "auto_approval_rate": round(approved / total * 100, 2),
        })

    return (
        pd.DataFrame(rows)
        .sort_values("finished_transactions", ascending=False)
        .reset_index(drop=True)
    )


def build_platform_stage_dropoff(df: pd.DataFrame) -> pd.DataFrame:
    """Where cancellations happen on each known platform."""

    cancelled = df[
        (df["status"] == "user_cancelled")
        & df["platform_normalized"].isin(KNOWN_PLATFORMS)
    ]

    summary = (
        cancelled.groupby(["platform_normalized", "stage"])
        .size()
        .reset_index(name="cancellations")
    )

    totals = summary.groupby("platform_normalized")["cancellations"].transform(
        "sum"
    )

    summary["pct_of_platform_cancellations"] = (
        summary["cancellations"] / totals * 100
    ).round(2)

    return summary.sort_values(
        ["platform_normalized", "cancellations"],
        ascending=[True, False],
    ).reset_index(drop=True)


def build_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Daily volume by outcome group."""

    daily = (
        df.groupby(["created_date", "outcome_group"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=OUTCOME_ORDER, fill_value=0)
    )

    daily["total"] = daily.sum(axis=1)
    daily["approved_share_pct"] = (
        daily["Approved"] / daily["total"] * 100
    ).round(2)

    return daily.reset_index()


def build_hourly_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Average transactions per calendar day for each weekday-hour slot."""

    per_day_hour = (
        df.groupby(["created_date", "created_weekday", "created_hour"])
        .size()
        .reset_index(name="transactions")
    )

    # Count each calendar day once per weekday (including quiet hours).
    days = per_day_hour[["created_date", "created_weekday"]].drop_duplicates()

    grid = days.merge(
        pd.DataFrame({"created_hour": range(24)}),
        how="cross",
    )

    grid = grid.merge(
        per_day_hour,
        on=["created_date", "created_weekday", "created_hour"],
        how="left",
    ).fillna({"transactions": 0})

    profile = (
        grid.groupby(["created_weekday", "created_hour"])["transactions"]
        .mean()
        .round(1)
        .reset_index(name="avg_transactions_per_day")
    )

    profile["weekday"] = profile["created_weekday"].map(
        dict(enumerate(WEEKDAY_NAMES))
    )

    return profile[
        ["created_weekday", "weekday", "created_hour",
         "avg_transactions_per_day"]
    ]


def build_time_spent_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Journey duration statistics by status (seconds)."""

    timed = df.dropna(subset=["time_spent_seconds"])

    summary = (
        timed.groupby("status")["time_spent_seconds"]
        .agg(
            transactions="size",
            median_seconds="median",
            p25_seconds=lambda s: s.quantile(0.25),
            p75_seconds=lambda s: s.quantile(0.75),
            p90_seconds=lambda s: s.quantile(0.90),
        )
        .round(1)
        .reset_index()
        .sort_values("transactions", ascending=False)
        .reset_index(drop=True)
    )

    return summary


def build_sdk_summary(df: pd.DataFrame, min_transactions: int = 500):
    """Approval and cancellation by SDK version (completed-flow only)."""

    finished = df[df["source"] == "finishTransaction"]

    rows = []

    for sdk, group in finished.groupby("sdk_version"):
        total = len(group)
        rows.append({
            "sdk_version": sdk,
            "finished_transactions": total,
            "auto_approval_rate": round(
                (group["status"] == "auto_approved").mean() * 100, 2
            ),
            "cancellation_rate": round(
                (group["status"] == "user_cancelled").mean() * 100, 2
            ),
            "sufficient_volume": total >= min_transactions,
        })

    return (
        pd.DataFrame(rows)
        .sort_values("finished_transactions", ascending=False)
        .reset_index(drop=True)
    )


def build_update_activity_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Median/p90 update count per outcome group (definition unverified)."""

    summary = (
        df.dropna(subset=["total_transaction_updates"])
        .groupby("outcome_group")["total_transaction_updates"]
        .agg(
            transactions="size",
            median_updates="median",
            p90_updates=lambda s: s.quantile(0.90),
        )
        .reset_index()
    )

    summary["outcome_group"] = pd.Categorical(
        summary["outcome_group"], categories=OUTCOME_ORDER, ordered=True
    )

    return summary.sort_values("outcome_group").reset_index(drop=True)


def build_manual_review_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Size and outcome of the manual (agent) decision queue."""

    manual = df[df["source"] == "application-update-by-agent"]

    summary = (
        manual.groupby("status")
        .size()
        .reset_index(name="transactions")
        .sort_values("transactions", ascending=False)
    )

    summary["pct_of_manual_decisions"] = (
        summary["transactions"] / max(len(manual), 1) * 100
    ).round(2)

    summary["pct_of_all_transactions"] = (
        summary["transactions"] / len(df) * 100
    ).round(2)

    return summary.reset_index(drop=True)


def build_behaviour_summaries(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return all behaviour summaries keyed by output filename."""

    return {
        "stage_dropoff_summary.csv": build_stage_dropoff_summary(df),
        "platform_cancellation_summary.csv": (
            build_platform_cancellation_summary(df)
        ),
        "platform_stage_dropoff.csv": build_platform_stage_dropoff(df),
        "daily_outcome_summary.csv": build_daily_summary(df),
        "hourly_activity_profile.csv": build_hourly_profile(df),
        "time_spent_summary.csv": build_time_spent_summary(df),
        "sdk_version_summary.csv": build_sdk_summary(df),
        "update_activity_summary.csv": build_update_activity_summary(df),
        "manual_review_summary.csv": build_manual_review_summary(df),
        "cleaning_log.csv": build_cleaning_log(df),
    }


def write_summaries(
    summaries: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    """Write summaries to CSV and echo them to the terminal."""

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, summary in summaries.items():
        summary.to_csv(output_dir / filename, index=False)
        print(f"\n{filename}")
        print(summary.to_string(index=False))
