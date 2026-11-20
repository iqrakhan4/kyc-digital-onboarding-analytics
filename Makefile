# KYC & Digital Onboarding Funnel Analytics
# Run `make help` to list targets.

PY := .venv/bin/python

.DEFAULT_GOAL := help
.PHONY: help setup setup-notebooks test demo export-powerbi notebooks reconcile real check-privacy clean

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup:  ## Create .venv and install dependencies
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

setup-notebooks:  ## Install the extra packages needed to run notebooks
	$(PY) -m pip install -r requirements-notebooks.txt

test:  ## Run the automated test suite
	$(PY) -m pytest -v

demo:  ## Run the full pipeline on SYNTHETIC data (no private data needed)
	$(PY) -m src.data_generation.generate_synthetic_data
	$(PY) -m src.pipeline --source synthetic

export-powerbi:  ## Export the Power BI data model from SYNTHETIC data
	$(PY) -m src.data_generation.generate_synthetic_data
	$(PY) -m src.export.export_powerbi_data --source synthetic

notebooks:  ## Re-execute both notebooks in place (needs setup-notebooks)
	cd notebooks && ../$(PY) -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=300 *.ipynb

reconcile:  ## Compare transaction IDs across private extracts (needs data/raw)
	$(PY) -m src.analysis.reconcile_datasets

real: reconcile  ## Run the full pipeline on PRIVATE data (needs data/raw + local config)
	$(PY) -m src.pipeline --source real

check-privacy:  ## Fail if private files or banned terms are tracked by git
	$(PY) scripts/check_public_safety.py

clean:  ## Remove generated outputs (keeps raw data and committed charts)
	rm -rf data/processed/* data/synthetic/* .pytest_cache
	touch data/processed/.gitkeep data/synthetic/.gitkeep
