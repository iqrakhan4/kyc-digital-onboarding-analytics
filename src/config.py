"""Shared project configuration.

Centralises filesystem paths and the loading of *local* (git-ignored)
configuration so that no script needs to hard-code private filenames.

Two kinds of local configuration are supported:

* ``config/dataset_manifest.local.json`` - maps logical dataset names to the
  private CSV filenames in ``data/raw/``.
* ``config/stage_mapping.local.json``    - maps raw workflow-module strings to
  generic, public-safe stage labels. Falls back to the committed
  ``*.example.json`` template when no local file exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CONFIG_DIR = ROOT / "config"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
FIGURES_DIR = ROOT / "reports" / "figures"
SQL_DIR = ROOT / "sql"

MANIFEST_PATH = CONFIG_DIR / "dataset_manifest.local.json"
STAGE_MAPPING_LOCAL = CONFIG_DIR / "stage_mapping.local.json"
STAGE_MAPPING_EXAMPLE = CONFIG_DIR / "stage_mapping.example.json"

SYNTHETIC_ONBOARDING_FILE = SYNTHETIC_DIR / "synthetic_onboarding.csv"


# --------------------------------------------------------------------------- #
# Dataset manifest
# --------------------------------------------------------------------------- #
def load_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load the local dataset manifest."""

    manifest_path = Path(path) if path else MANIFEST_PATH

    if not manifest_path.exists():
        raise FileNotFoundError(
            "Local dataset manifest not found. Copy "
            "config/dataset_manifest.example.json to "
            "config/dataset_manifest.local.json and edit the filenames."
        )

    with open(manifest_path, encoding="utf-8") as file:
        manifest = json.load(file)

    if "datasets" not in manifest:
        raise ValueError("Manifest must contain a 'datasets' list.")

    return manifest


def get_dataset_config(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the manifest entry for ``name``."""

    for dataset in manifest["datasets"]:
        if dataset["name"] == name:
            return dataset

    raise KeyError(f"Dataset '{name}' is not defined in the manifest.")


def dataset_file(
    manifest: dict[str, Any],
    name: str,
    raw_dir: Path | None = None,
) -> Path:
    """Return the absolute CSV path for a manifest dataset."""

    directory = Path(raw_dir) if raw_dir else RAW_DIR
    return directory / get_dataset_config(manifest, name)["file"]


def display_names(manifest: dict[str, Any]) -> dict[str, str]:
    """Map dataset names to public-safe display names."""

    return {
        dataset["name"]: dataset.get(
            "display_name",
            dataset["name"].replace("_", " ").capitalize(),
        )
        for dataset in manifest["datasets"]
    }


# --------------------------------------------------------------------------- #
# Stage mapping
# --------------------------------------------------------------------------- #
def load_stage_mapping(path: Path | None = None) -> dict[str, Any]:
    """Load the module-to-stage mapping (local file preferred)."""

    if path:
        mapping_path = Path(path)
    elif STAGE_MAPPING_LOCAL.exists():
        mapping_path = STAGE_MAPPING_LOCAL
    else:
        mapping_path = STAGE_MAPPING_EXAMPLE

    with open(mapping_path, encoding="utf-8") as file:
        mapping = json.load(file)

    mapping.setdefault("default_stage", "Other")
    mapping.setdefault("missing_stage", "No stage recorded")
    mapping.setdefault("rules", [])

    return mapping
