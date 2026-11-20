
import pandas as pd
import pytest
import src.analysis.analyze_onboarding_funnel as funnel

from src.analysis.analyze_onboarding_funnel import (
    build_status_summary,
    build_source_status_summary,
    build_platform_status_summary,
    build_kpi_summary,
    build_automated_platform_summary,
)


@pytest.fixture
def sample_data():
    """Create synthetic onboarding records for testing."""

    records = [
        ("T001", "auto_approved", "finishTransaction", "android"),
        ("T002", "auto_approved", "finishTransaction", "android"),
        ("T003", "auto_declined", "finishTransaction", "android"),
        ("T004", "auto_approved", "finishTransaction", "ios"),
        ("T005", "auto_declined", "finishTransaction", "ios"),
        ("T006", "manually_approved", "application-update-by-agent", "missing"),
        ("T007", "manually_declined", "application-update-by-agent", "missing"),
        ("T008", "user_cancelled", "finishTransaction", "android"),
        ("T009", "started", "createForRequest", "ios"),
        ("T010", "error", "finishTransaction", "windows"),
        ("T011", "needs_review", "finishTransaction", "macos"),
    ]

    return pd.DataFrame(
        records,
        columns=[
            "transaction_id",
            "status",
            "source",
            "platform_normalized",
        ],
    )

def run_loader_with_data(monkeypatch, tmp_path, df):
    """Run the data loader using a temporary synthetic CSV."""

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    csv_file = raw_dir / "query_result_2026-05-12-test.csv"
    df.to_csv(csv_file, index=False)

    monkeypatch.setattr(funnel, "RAW_DIR", raw_dir)

    return funnel.load_onboarding_data()


def valid_loader_data():
    """Return a minimal valid dataset for loader tests."""

    return pd.DataFrame([
        {
            "transaction_id": "T001",
            "status": "auto_approved",
            "source": "finishTransaction",
            "platform": "android",
        },
        {
            "transaction_id": "T002",
            "status": "started",
            "source": "createForRequest",
            "platform": "ios",
        },
    ])

def test_status_summary(sample_data):
    """Verify transaction counts and percentages by status."""

    summary = build_status_summary(sample_data)

    assert summary["transactions"].sum() == 11
    assert summary["percentage"].sum() == pytest.approx(
    100.0,
    abs=0.02,
)

    approved = summary.loc[
        summary["status"] == "auto_approved",
        "transactions",
    ].iloc[0]

    assert approved == 3


def test_source_status_summary(sample_data):
    """Verify status aggregation within each source."""

    summary = build_source_status_summary(sample_data)

    source_totals = (
        summary.groupby("source")["transactions"].sum()
    )

    assert source_totals["finishTransaction"] == 8
    assert source_totals["application-update-by-agent"] == 2
    assert source_totals["createForRequest"] == 1

    assert (
        summary["percentage_within_source"].between(0, 100).all()
    )


def test_platform_status_summary(sample_data):
    """Verify platform-level transaction aggregation."""

    summary = build_platform_status_summary(sample_data)

    platform_totals = (
        summary.groupby("platform_normalized")["transactions"].sum()
    )

    assert platform_totals["android"] == 4
    assert platform_totals["ios"] == 3
    assert platform_totals["missing"] == 2

def test_loader_rejects_duplicate_transaction_ids(monkeypatch, tmp_path):
    """Reject duplicate transaction identifiers."""

    df = valid_loader_data()
    df.loc[1, "transaction_id"] = "T001"

    with pytest.raises(ValueError, match="duplicate transaction IDs"):
        run_loader_with_data(monkeypatch, tmp_path, df)


def test_loader_rejects_missing_transaction_ids(monkeypatch, tmp_path):
    """Reject missing transaction identifiers."""

    df = valid_loader_data()
    df.loc[0, "transaction_id"] = None

    with pytest.raises(ValueError, match="missing values"):
        run_loader_with_data(monkeypatch, tmp_path, df)


def test_loader_rejects_missing_status(monkeypatch, tmp_path):
    """Reject records without a transaction status."""

    df = valid_loader_data()
    df.loc[0, "status"] = None

    with pytest.raises(ValueError, match="Status or source"):
        run_loader_with_data(monkeypatch, tmp_path, df)


def test_loader_rejects_unexpected_status(monkeypatch, tmp_path):
    """Reject transaction statuses outside the expected set."""

    df = valid_loader_data()
    df.loc[0, "status"] = "unexpected_status"

    with pytest.raises(ValueError, match="Unexpected transaction statuses"):
        run_loader_with_data(monkeypatch, tmp_path, df)

def test_kpi_summary(sample_data):
    """Verify headline onboarding KPI calculations."""

    summary = build_kpi_summary(sample_data)

    metrics = summary.set_index("metric")["value"]

    assert metrics["total_transactions"] == 11
    assert metrics["approved_transactions"] == 4
    assert metrics["declined_transactions"] == 3
    assert metrics["cancelled_transactions"] == 1
    assert metrics["started_transactions"] == 1
    assert metrics["error_transactions"] == 1
    assert metrics["needs_review_transactions"] == 1

    assert metrics["approval_share_all_transactions"] == pytest.approx(36.36)
    assert metrics["approval_rate_among_decided"] == pytest.approx(57.14)
    assert metrics["decline_share_all_transactions"] == pytest.approx(27.27)
    assert metrics["cancellation_share_all_transactions"] == pytest.approx(9.09)


def test_automated_platform_summary(sample_data):
    """Verify automated approval rates for known platforms."""

    summary = build_automated_platform_summary(sample_data)

    platforms = summary.set_index("platform_normalized")

    assert platforms.loc["android", "auto_approved"] == 2
    assert platforms.loc["android", "auto_declined"] == 1
    assert platforms.loc["android", "decided_transactions"] == 3
    assert platforms.loc["android", "automated_approval_rate"] == pytest.approx(66.67)

    assert platforms.loc["ios", "automated_approval_rate"] == pytest.approx(50.00)

    # Platforms without automated decisions should not appear.
    assert "windows" not in platforms.index
    assert "macos" not in platforms.index
    assert "missing" not in platforms.index
