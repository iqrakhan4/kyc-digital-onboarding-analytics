"""End-to-end analysis pipeline.

Usage (from the project root)::

    python -m src.pipeline --source synthetic   # public demo, no private data
    python -m src.pipeline --source real        # private extracts in data/raw

Steps
-----
1. Load and validate the transaction-level extract.
2. Clean / enrich (timestamps, durations, generic stage labels).
3. Build funnel + behaviour summaries (CSV, aggregate only).
4. Run the SQL analysis layer and check it agrees with pandas.
5. Render charts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.analysis.analyze_onboarding_funnel import (
    OPTIONAL_COLUMNS,
    build_all_summaries,
    load_onboarding_data,
)
from src.analysis.onboarding_behaviour import (
    build_behaviour_summaries,
    enrich_onboarding_data,
    write_summaries,
)
from src.config import (
    FIGURES_DIR,
    PROCESSED_DIR,
    SYNTHETIC_ONBOARDING_FILE,
    display_names,
    load_manifest,
)
from src.data_generation.generate_synthetic_data import (
    main as generate_synthetic,
)
from src.database.run_sql_analysis import run_sql_analysis
from src.export.export_powerbi_data import export_powerbi_data
from src.visualization.make_charts import make_all_charts


def run(source: str = "real", rows: int = 25_000, seed: int = 42) -> None:
    synthetic = source == "synthetic"

    if synthetic:
        output_dir = PROCESSED_DIR / "synthetic"
        figures_dir = output_dir / "figures"
        source_label = "Generated dataset"

        if not SYNTHETIC_ONBOARDING_FILE.exists():
            generate_synthetic(rows=rows, seed=seed)

        path = SYNTHETIC_ONBOARDING_FILE
    else:
        output_dir = PROCESSED_DIR
        figures_dir = FIGURES_DIR
        source_label = "Onboarding transactions extract"
        path = None

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"ONBOARDING ANALYTICS PIPELINE  ({source} data)")
    print("=" * 70)

    # 1-2. Load, validate, enrich ----------------------------------------
    df = load_onboarding_data(path=path, extra_columns=OPTIONAL_COLUMNS)
    df = enrich_onboarding_data(df)

    # 3. Summaries --------------------------------------------------------
    print("\n[1/4] Funnel summaries")
    for filename, summary in build_all_summaries(df).items():
        summary.to_csv(output_dir / filename, index=False)
        print(f"  wrote {filename}")

    print("\n[2/4] Behaviour summaries")
    behaviour = build_behaviour_summaries(df)
    write_summaries(behaviour, output_dir)

    # 4. SQL layer --------------------------------------------------------
    print("\n[3/4] SQL analysis layer")
    run_sql_analysis(df, output_dir / "sql_results", output_dir / "onboarding.db")

    # 5. Power BI export + charts -----------------------------------------------------------
    overlap = None
    names = None
    overlap_file = output_dir / "dataset_overlap_report.csv"

    if not synthetic and overlap_file.exists():
        overlap = pd.read_csv(overlap_file)
        try:
            names = display_names(load_manifest())
        except FileNotFoundError:
            names = None

    print("\n[4/4] Power BI data export")
    export_powerbi_data(df, output_dir / "powerbi", overlap=overlap, names=names)

    paths = make_all_charts(
        df,
        figures_dir,
        source_label=source_label,
        synthetic=synthetic,
        overlap=overlap,
        names=names,
    )

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"Summaries : {output_dir}")
    print(f"Figures   : {figures_dir}")
    for chart in paths:
        print(f"  - {Path(chart).name}")
    print("\nOnly aggregate data was exported. No identifiers were written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["real", "synthetic"],
                        default="real")
    parser.add_argument("--rows", type=int, default=25_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(source=args.source, rows=args.rows, seed=args.seed)
