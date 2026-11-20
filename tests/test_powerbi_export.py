"""Tests for the Power BI export.

Power BI's DAX cannot be executed here, so the measure *logic* from
powerbi/dax_measures.md is emulated in pandas on the exported cube and compared
with the independently computed summaries. Referential integrity is also
checked, because orphaned fact keys appear as blank rows in Power BI.
"""

import pandas as pd
import pytest

from src.analysis.onboarding_behaviour import (
    build_platform_cancellation_summary,
    build_stage_dropoff_summary,
)
from src.export.export_powerbi_data import (
    build_dataset_overlap,
    build_fact_table,
    export_powerbi_data,
)


@pytest.fixture(scope="module")
def tables(enriched, tmp_path_factory):
    out = tmp_path_factory.mktemp("powerbi")
    return export_powerbi_data(enriched, out)


def test_cube_reproduces_source_totals(enriched, tables):
    fact = tables["fact_onboarding"]

    assert fact["transactions"].sum() == len(enriched)
    assert fact.groupby("status")["transactions"].sum().to_dict() == (
        enriched["status"].value_counts().to_dict()
    )


def test_no_identifier_columns_exported(tables):
    for name, table in tables.items():
        assert not any("transaction_id" in c for c in table.columns), name


def test_cube_is_smaller_than_source(enriched, tables):
    assert len(tables["fact_onboarding"]) < len(enriched)


def test_referential_integrity(tables):
    fact = tables["fact_onboarding"]

    for column, dim, key in [
        ("created_date", "dim_date", "date"),
        ("status", "dim_status", "status"),
        ("platform", "dim_platform", "platform"),
        ("stage", "dim_stage", "stage"),
    ]:
        missing = set(fact[column]) - set(tables[dim][key])
        assert not missing, f"{column} values missing from {dim}: {missing}"


def test_dimension_keys_are_unique(tables):
    for dim, key in [("dim_date", "date"), ("dim_status", "status"),
                     ("dim_platform", "platform"), ("dim_stage", "stage")]:
        assert tables[dim][key].is_unique, dim


def test_dax_logic_approval_and_cancellation_share(enriched, tables):
    fact = tables["fact_onboarding"].merge(
        tables["dim_status"], on="status"
    )
    total = fact["transactions"].sum()

    approved = fact.loc[fact["is_approved"] == 1, "transactions"].sum()
    declined = fact.loc[fact["is_declined"] == 1, "transactions"].sum()
    cancelled = fact.loc[fact["status"] == "user_cancelled",
                         "transactions"].sum()

    assert approved / total == pytest.approx(
        enriched["status"].isin(["auto_approved", "manually_approved"]).mean()
    )
    assert approved / (approved + declined) == pytest.approx(
        approved / (approved + enriched["status"].isin(
            ["auto_declined", "manually_declined"]).sum())
    )
    assert cancelled / total == pytest.approx(
        (enriched["status"] == "user_cancelled").mean()
    )


def test_dax_logic_finished_cancellation_rate_by_platform(enriched, tables):
    fact = tables["fact_onboarding"]
    finished = fact[fact["source"] == "finishTransaction"]

    emulated = (
        finished.groupby("platform")
        .apply(
            lambda g: g.loc[g["status"] == "user_cancelled",
                            "transactions"].sum() / g["transactions"].sum(),
            include_groups=False,
        )
    )

    expected = build_platform_cancellation_summary(enriched).set_index(
        "platform"
    )["cancellation_rate"]

    for platform, rate in expected.items():
        assert emulated[platform] * 100 == pytest.approx(rate, abs=0.01)


def test_dax_logic_cancellation_share_by_stage(enriched, tables):
    fact = tables["fact_onboarding"]
    cancelled = fact[fact["status"] == "user_cancelled"]

    share = (
        cancelled.groupby("stage")["transactions"].sum()
        / cancelled["transactions"].sum()
        * 100
    )

    expected = build_stage_dropoff_summary(enriched).set_index("stage")[
        "pct_of_status"
    ]

    for stage, pct in expected.items():
        assert share[stage] == pytest.approx(pct, abs=0.01)


def test_dax_logic_average_journey(enriched, tables):
    fact = tables["fact_onboarding"]

    emulated = (
        fact["time_spent_sum_seconds"].sum() / fact["time_spent_count"].sum()
    )

    assert emulated == pytest.approx(
        enriched["time_spent_seconds"].mean(), rel=1e-3
    )


def test_dim_date_weekday_matches_calendar(tables):
    dim_date = tables["dim_date"]
    parsed = pd.to_datetime(dim_date["date"])

    assert (dim_date["weekday_number"] == parsed.dt.day_of_week + 1).all()
    assert len(dim_date) == (parsed.max() - parsed.min()).days + 1


def test_overlap_export_contains_both_directions():
    overlap = pd.DataFrame([{
        "dataset_a": "a", "dataset_b": "b",
        "unique_ids_a": 100, "unique_ids_b": 80,
        "overlapping_transaction_ids": 60,
        "overlap_pct_of_a": 60.0, "overlap_pct_of_b": 75.0,
        "jaccard_similarity_pct": 50.0,
    }])

    result = build_dataset_overlap(overlap, {"a": "Alpha", "b": "Beta"})
    lookup = result.set_index(["row_dataset", "column_dataset"])

    assert len(result) == 2
    assert lookup.loc[("Alpha", "Beta"), "pct_of_row_ids_in_column"] == 60.0
    assert lookup.loc[("Beta", "Alpha"), "pct_of_row_ids_in_column"] == 75.0
