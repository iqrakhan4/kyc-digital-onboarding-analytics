import json
from itertools import combinations
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MANIFEST_PATH = PROJECT_ROOT / "config" / "dataset_manifest.local.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


def load_dataset(dataset_config):
    """Load only the transaction identifier column."""

    name = dataset_config["name"]
    filename = dataset_config["file"]
    id_column = dataset_config["id_column"]

    file_path = RAW_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Dataset not found: {name}")

    # Read identifiers as strings to preserve their original format.
    df = pd.read_csv(
        file_path,
        usecols=[id_column],
        dtype={id_column: "string"},
    )

    identifiers = (
        df[id_column]
        .str.strip()
        .replace("", pd.NA)
        .dropna()
    )

    unique_ids = set(identifiers.unique())

    summary = {
        "dataset": name,
        "total_rows": len(df),
        "non_null_ids": len(identifiers),
        "unique_transaction_ids": len(unique_ids),
        "repeated_id_occurrences": len(identifiers) - len(unique_ids),
        "missing_ids": int(df[id_column].isna().sum()),
    }

    return summary, unique_ids


def calculate_overlaps(dataset_ids):
    """Calculate pairwise transaction identifier overlaps."""

    results = []

    for (name_a, ids_a), (name_b, ids_b) in combinations(
        dataset_ids.items(), 2
    ):
        common_ids = ids_a.intersection(ids_b)
        union_ids = ids_a.union(ids_b)

        results.append({
            "dataset_a": name_a,
            "dataset_b": name_b,
            "unique_ids_a": len(ids_a),
            "unique_ids_b": len(ids_b),
            "overlapping_transaction_ids": len(common_ids),
            "overlap_pct_of_a": round(
                len(common_ids) / len(ids_a) * 100, 2
            ) if ids_a else 0,
            "overlap_pct_of_b": round(
                len(common_ids) / len(ids_b) * 100, 2
            ) if ids_b else 0,
            "jaccard_similarity_pct": round(
                len(common_ids) / len(union_ids) * 100, 2
            ) if union_ids else 0,
        })

    return results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "Local manifest not found. Create config/"
            "dataset_manifest.local.json first."
        )

    with open(MANIFEST_PATH, encoding="utf-8") as file:
        manifest = json.load(file)

    dataset_summaries = []
    dataset_ids = {}

    print("Starting transaction-level dataset reconciliation.")

    for dataset_config in manifest["datasets"]:
        summary, unique_ids = load_dataset(dataset_config)

        dataset_summaries.append(summary)
        dataset_ids[summary["dataset"]] = unique_ids

        print(
            f"{summary['dataset']}: "
            f"{summary['total_rows']:,} rows, "
            f"{summary['unique_transaction_ids']:,} unique IDs"
        )

    overlap_results = calculate_overlaps(dataset_ids)

    summary_df = pd.DataFrame(dataset_summaries)
    overlap_df = pd.DataFrame(overlap_results)

    summary_df.to_csv(
        OUTPUT_DIR / "reconciliation_summary.csv",
        index=False,
    )

    overlap_df.to_csv(
        OUTPUT_DIR / "dataset_overlap_report.csv",
        index=False,
    )

    print("\n" + "=" * 55)
    print("DATASET RECONCILIATION COMPLETED")
    print("=" * 55)

    print("\nDataset summary:")
    print(summary_df.to_string(index=False))

    print("\nPairwise overlap:")
    print(
        overlap_df.sort_values(
            "overlapping_transaction_ids",
            ascending=False,
        ).to_string(index=False)
    )

    print("\nReports saved locally in data/processed/")


if __name__ == "__main__":
    main()
