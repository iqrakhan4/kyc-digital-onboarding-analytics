import pandas as pd

from src.analysis.analyze_onboarding_funnel import (
    EXPECTED_STATUSES,
    OPTIONAL_COLUMNS,
    load_onboarding_data,
)
from src.analysis.onboarding_behaviour import enrich_onboarding_data
from src.data_generation.generate_synthetic_data import (
    generate_onboarding_data,
)
from src.database.run_sql_analysis import run_sql_analysis


def test_generator_is_deterministic_and_valid():
    first = generate_onboarding_data(rows=500, seed=1)
    second = generate_onboarding_data(rows=500, seed=1)

    pd.testing.assert_frame_equal(first, second)
    assert first["transaction_id"].is_unique
    assert set(first["status"]) <= EXPECTED_STATUSES
    assert first["transaction_id"].str.startswith("SYN-").all()


def test_sql_results_match_pandas(enriched, tmp_path):
    results = run_sql_analysis(
        enriched, tmp_path / "out", tmp_path / "test.db", verify=True
    )

    assert int(results["02_headline_kpis"].loc[0, "total_transactions"]) == (
        len(enriched)
    )
    assert (tmp_path / "out" / "01_outcome_summary.csv").exists()


def test_sql_load_handles_missing_platform_values(tmp_path, example_mapping):
    """Regression: raw NaN platforms once broke the NOT NULL table load."""

    raw = generate_onboarding_data(rows=300, seed=3)
    raw.loc[raw.index[:25], "platform"] = None
    csv = tmp_path / "with_missing.csv"
    raw.to_csv(csv, index=False)

    df = load_onboarding_data(
        path=csv, extra_columns=OPTIONAL_COLUMNS, verbose=False
    )
    df = enrich_onboarding_data(df, stage_mapping=example_mapping)

    results = run_sql_analysis(
        df, tmp_path / "out", tmp_path / "db.sqlite", verify=True
    )

    platforms = set(results["03_platform_cancellation"]["platform"])
    assert "missing" in platforms


def test_charts_render_without_error(enriched, tmp_path):
    from src.visualization.make_charts import make_all_charts

    paths = make_all_charts(enriched, tmp_path, "Test data", synthetic=True)

    assert len(paths) == 7
    assert all(path.exists() and path.stat().st_size > 5_000 for path in paths)
