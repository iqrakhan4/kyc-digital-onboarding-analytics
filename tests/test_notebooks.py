"""Guard the committed notebooks against silent failures.

A notebook can 'run successfully' while displaying nothing (for example when a
plotting backend is overridden), or can embed machine paths and warnings. These
tests read the saved outputs, so they run without Jupyter installed.
"""

import json
from pathlib import Path

import pytest

NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))

EXPECTED_MIN_IMAGES = {
    "01_onboarding_funnel_exploration.ipynb": 4,
    "02_data_quality_and_validation.ipynb": 1,
}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_notebooks_exist():
    assert {n.name for n in NOTEBOOKS} >= set(EXPECTED_MIN_IMAGES)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_has_no_error_outputs(path):
    for cell in _load(path)["cells"]:
        for output in cell.get("outputs", []):
            assert output.get("output_type") != "error", path.name


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_charts_actually_rendered(path):
    images = sum(
        "image/png" in output.get("data", {})
        for cell in _load(path)["cells"]
        for output in cell.get("outputs", [])
    )

    assert images >= EXPECTED_MIN_IMAGES.get(path.name, 0), (
        f"{path.name} rendered {images} charts"
    )


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_has_no_machine_paths_or_warnings(path):
    text = path.read_text(encoding="utf-8")

    for forbidden in ("/home/", "/root/", "/tmp/", "/Users/", "C:\\Users",
                      "Warning"):
        assert forbidden not in text, f"{path.name} contains {forbidden!r}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_defaults_to_synthetic_data(path):
    source = "".join(
        "".join(cell["source"])
        for cell in _load(path)["cells"]
        if cell["cell_type"] == "code"
    )

    if "SOURCE =" in source:
        assert 'SOURCE = "synthetic"' in source
