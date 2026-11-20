"""Run the SQL analysis layer against a local SQLite database.

The SQL in ``sql/`` is written in portable ANSI-style SQL. This module:

1. creates the analytical table (``sql/schema``),
2. loads the cleaned DataFrame into it,
3. creates views (``sql/views``),
4. runs every query in ``sql/analysis`` and saves aggregate results, and
5. verifies that the SQL results agree with the pandas results.

Step 5 is a reconciliation control: two independent implementations of the
same metric must give identical answers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.analysis.onboarding_behaviour import (
    build_platform_cancellation_summary,
    build_stage_dropoff_summary,
)
from src.config import SQL_DIR

TABLE_COLUMNS = [
    "transaction_id",
    "status",
    "source",
    "platform",
    "sdk_version",
    "stage",
    "created_date",
    "created_hour",
    "time_spent_seconds",
    "total_transaction_updates",
]


def _prepare_table_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Select and rename the columns that make up the analytical table."""

    # The raw 'platform' column may contain NaN; the analytical table uses the
    # normalised version, so drop the raw column before renaming to avoid a
    # duplicate column name.
    frame = (
        df.drop(columns=["platform"], errors="ignore")
        .rename(columns={"platform_normalized": "platform"})
        .copy()
    )

    for column in TABLE_COLUMNS:
        if column not in frame:
            frame[column] = None

    return frame[TABLE_COLUMNS]


def _run_script_files(connection: sqlite3.Connection, directory: Path) -> None:
    for sql_file in sorted(directory.glob("*.sql")):
        connection.executescript(sql_file.read_text(encoding="utf-8"))


def build_database(df: pd.DataFrame, db_path: Path) -> sqlite3.Connection:
    """Create (or rebuild) the SQLite analytical database."""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    connection = sqlite3.connect(db_path)

    _run_script_files(connection, SQL_DIR / "schema")

    _prepare_table_frame(df).to_sql(
        "onboarding_transactions",
        connection,
        if_exists="append",
        index=False,
        chunksize=10_000,
    )

    _run_script_files(connection, SQL_DIR / "views")
    connection.commit()

    return connection


def run_queries(connection: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    """Execute every analysis query and return the results by file stem."""

    results = {}

    for sql_file in sorted((SQL_DIR / "analysis").glob("*.sql")):
        results[sql_file.stem] = pd.read_sql_query(
            sql_file.read_text(encoding="utf-8"), connection
        )

    return results


def verify_against_pandas(
    results: dict[str, pd.DataFrame],
    df: pd.DataFrame,
) -> list[str]:
    """Check the SQL output equals the pandas implementation.

    Returns a list of passed check descriptions; raises AssertionError on
    the first disagreement.
    """

    passed = []

    # 1. Outcome counts -------------------------------------------------
    sql_counts = results["01_outcome_summary"].set_index("status")[
        "transactions"
    ]
    pandas_counts = df["status"].value_counts()

    assert sql_counts.sort_index().to_dict() == (
        pandas_counts.sort_index().to_dict()
    ), "Outcome counts differ between SQL and pandas"
    passed.append("Outcome counts match")

    # 2. Total / approved -------------------------------------------------
    kpi = results["02_headline_kpis"].iloc[0]
    assert int(kpi["total_transactions"]) == len(df)
    assert int(kpi["approved_transactions"]) == int(
        df["status"].isin({"auto_approved", "manually_approved"}).sum()
    )
    passed.append("Headline KPI counts match")

    # 3. Platform cancellations -----------------------------------------
    sql_platform = results["03_platform_cancellation"].set_index("platform")
    pandas_platform = build_platform_cancellation_summary(df).set_index(
        "platform"
    )

    for platform, row in pandas_platform.iterrows():
        assert int(sql_platform.loc[platform, "cancelled"]) == int(
            row["cancelled"]
        ), f"Cancellation count differs for {platform}"
        assert float(sql_platform.loc[platform, "cancellation_rate"]) == (
            float(row["cancellation_rate"])
        ), f"Cancellation rate differs for {platform}"
    passed.append("Platform cancellation counts and rates match")

    # 4. Stage drop-off --------------------------------------------------
    sql_stage = results["04_stage_dropoff"].set_index("stage")[
        "transactions"
    ]
    pandas_stage = build_stage_dropoff_summary(df).set_index("stage")[
        "transactions"
    ]

    assert sql_stage.sort_index().to_dict() == (
        pandas_stage.sort_index().to_dict()
    ), "Stage drop-off counts differ between SQL and pandas"
    passed.append("Stage drop-off counts match")

    return passed


def run_sql_analysis(
    df: pd.DataFrame,
    results_dir: Path,
    db_path: Path,
    verify: bool = True,
) -> dict[str, pd.DataFrame]:
    """Build the database, run all queries, save and verify the results."""

    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    connection = build_database(df, db_path)

    try:
        results = run_queries(connection)
    finally:
        connection.close()

    for name, result in results.items():
        result.to_csv(results_dir / f"{name}.csv", index=False)
        print(f"  ran sql/analysis/{name}.sql -> {len(result)} rows")

    if verify:
        for message in verify_against_pandas(results, df):
            print(f"  [verified] {message}")

    return results
