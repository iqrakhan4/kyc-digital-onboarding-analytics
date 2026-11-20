"""Shared fixtures. Tests use only synthetic data - never private extracts."""

import pytest

from src.analysis.analyze_onboarding_funnel import (
    OPTIONAL_COLUMNS,
    load_onboarding_data,
)
from src.analysis.onboarding_behaviour import enrich_onboarding_data
from src.config import STAGE_MAPPING_EXAMPLE, load_stage_mapping
from src.data_generation.generate_synthetic_data import (
    generate_onboarding_data,
)


@pytest.fixture(scope="session")
def example_mapping():
    """Always use the committed template so results are deterministic."""
    return load_stage_mapping(STAGE_MAPPING_EXAMPLE)


@pytest.fixture(scope="session")
def synthetic_csv(tmp_path_factory):
    path = tmp_path_factory.mktemp("synthetic") / "synthetic.csv"
    generate_onboarding_data(rows=4000, seed=7).to_csv(path, index=False)
    return path


@pytest.fixture(scope="session")
def enriched(synthetic_csv, example_mapping):
    df = load_onboarding_data(
        path=synthetic_csv,
        extra_columns=OPTIONAL_COLUMNS,
        verbose=False,
    )
    return enrich_onboarding_data(df, stage_mapping=example_mapping)
