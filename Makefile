# demo-gx pipeline — unified command entry points.
# Usage: make setup | data | run | test | clean

PYTHON := .venv/bin/python
INPUT  := data/sample_data.json
ENV    ?= dev

.PHONY: setup data run test clean

## First run only: create the virtualenv and install the package in editable mode.
## Dependencies are declared once in pyproject.toml; there is no separate lock file.
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -e ".[dev]"

## Generate sample input data (data/sample_data.json)
data:
	$(PYTHON) scripts/generate_sample_data.py

## Run the full pipeline (override env: ENV=test make run)
run: data
	$(PYTHON) -m demo_gx.cli --input $(INPUT) --env $(ENV)

## Run the pytest suite
test:
	$(PYTHON) -m pytest tests/ -v

## Remove ALL run artifacts (data/, test/data/, data_prod/ cover samples,
## metrics, and logs which all live under the env storage dirs)
clean:
	rm -rf data test/data data_prod
