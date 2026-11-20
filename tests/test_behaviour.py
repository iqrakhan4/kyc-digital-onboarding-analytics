import pandas as pd
import pytest

from src.analysis.onboarding_behaviour import (
    build_cleaning_log,
    build_daily_summary,
    build_manual_review_summary,
    build_platform_cancellation_summary,
    build_stage_dropoff_summary,
    build_time_spent_summary,
    classify_stage,
    parse_numeric,
    parse_timestamps,
)


def test_parse_numeric_handles_thousands_separator():
    result = parse_numeric(pd.Series(["75,206", "1,599", "12", None, "x"]))

    assert result.iloc[0] == 75206
    assert result.iloc[1] == 1599
    assert result.iloc[2] == 12
    assert pd.isna(result.iloc[3])
    assert pd.isna(result.iloc[4])


def test_parse_timestamps_export_format():
    parsed = parse_timestamps(
        pd.Series(["Mar 24, 2026, 12:17 AM", "Mar 27, 2026, 10:40 PM",
                   "Mar 24, 2026, 5:05 PM"])
    )

    assert parsed.iloc[0].hour == 0
    assert parsed.iloc[1].hour == 22
    assert parsed.iloc[2].hour == 17
    assert parsed.notna().all()


def test_classify_stage_rules_missing_and_default(example_mapping):
    assert classify_stage("module_ab_ip_geolocation_api", example_mapping) == (
        "Location check"
    )
    assert classify_stage("module_x_document_verification_form",
                          example_mapping) == "Document verification"
    assert classify_stage(None, example_mapping) == "No stage recorded"
    assert classify_stage("module_unknown_thing", example_mapping) == "Other"


def test_enrichment_flags_outliers_and_cleans(enriched):
    assert "stage" in enriched
    assert enriched["created_ts"].notna().all()
    assert enriched["total_transaction_updates"].notna().all()

    # Outliers are excluded from timing, never silently kept.
    assert enriched.loc[
        enriched["time_spent_outlier"], "time_spent_seconds"
    ].isna().all()
    assert enriched["time_spent_seconds"].max() <= 3600


def test_cleaning_log_reports_synthetic_quirks(enriched):
    log = build_cleaning_log(enriched).set_index("check")["records"]

    assert log["rows_processed"] == len(enriched)
    assert log["update_counts_with_separator"] == 1
    assert log["time_spent_outliers_excluded"] >= 1


def test_stage_dropoff_percentages_sum_to_100(enriched):
    summary = build_stage_dropoff_summary(enriched)

    cancelled = int((enriched["status"] == "user_cancelled").sum())

    assert summary["transactions"].sum() == cancelled
    assert summary["pct_of_status"].sum() == pytest.approx(100, abs=0.1)


def test_platform_cancellation_uses_finish_records_only(enriched):
    summary = build_platform_cancellation_summary(enriched)

    finished = int((enriched["source"] == "finishTransaction").sum())

    assert summary["finished_transactions"].sum() == finished
    assert summary["cancellation_rate"].between(0, 100).all()


def test_daily_summary_totals_reconcile(enriched):
    daily = build_daily_summary(enriched)

    assert daily["total"].sum() == len(enriched)
    assert daily["approved_share_pct"].between(0, 100).all()


def test_time_spent_summary_ordering(enriched):
    summary = build_time_spent_summary(enriched).set_index("status")

    # Users who cancel leave sooner than those who complete.
    assert (
        summary.loc["user_cancelled", "median_seconds"]
        < summary.loc["auto_approved", "median_seconds"]
    )
    assert (summary["p25_seconds"] <= summary["median_seconds"]).all()
    assert (summary["median_seconds"] <= summary["p90_seconds"]).all()


def test_manual_review_summary_only_agent_records(enriched):
    summary = build_manual_review_summary(enriched)

    agent_rows = int(
        (enriched["source"] == "application-update-by-agent").sum()
    )

    assert summary["transactions"].sum() == agent_rows
    assert set(summary["status"]) <= {"manually_approved",
                                      "manually_declined"}
