import pandas as pd
import pytest

import src.analysis.analyze_onboarding_funnel as funnel
from src.analysis.reconcile_datasets import calculate_overlaps


def _write(tmp_path, df, name="in.csv"):
    path = tmp_path / name
    df.to_csv(path, index=False)
    return path


def test_loader_reports_missing_required_columns(tmp_path):
    path = _write(tmp_path, pd.DataFrame({"transaction_id": ["T1"],
                                          "status": ["started"]}))

    with pytest.raises(ValueError, match="Missing required columns"):
        funnel.load_onboarding_data(path=path, verbose=False)


def test_loader_loads_optional_columns_only_when_present(tmp_path):
    df = pd.DataFrame({
        "transaction_id": ["T1"],
        "status": ["started"],
        "source": ["createForRequest"],
        "platform": [None],
        "created_at": ["Mar 01, 2026, 1:00 AM"],
    })

    loaded = funnel.load_onboarding_data(
        path=_write(tmp_path, df),
        extra_columns=("created_at", "does_not_exist"),
        verbose=False,
    )

    assert "created_at" in loaded
    assert "does_not_exist" not in loaded
    assert loaded.loc[0, "platform_normalized"] == "missing"


def test_overlap_metrics_match_worked_example():
    """The worked example from the project docs: 100 vs 80 IDs, 60 shared."""

    ids_a = {f"a{i}" for i in range(40)} | {f"s{i}" for i in range(60)}
    ids_b = {f"b{i}" for i in range(20)} | {f"s{i}" for i in range(60)}

    result = calculate_overlaps({"A": ids_a, "B": ids_b})[0]

    assert result["overlapping_transaction_ids"] == 60
    assert result["overlap_pct_of_a"] == 60.0
    assert result["overlap_pct_of_b"] == 75.0
    assert result["jaccard_similarity_pct"] == 50.0


def test_overlap_of_disjoint_and_empty_sets():
    result = calculate_overlaps({"A": {"1"}, "B": {"2"}, "C": set()})

    assert all(r["overlapping_transaction_ids"] == 0 for r in result)
    assert all(r["jaccard_similarity_pct"] == 0 for r in result)
