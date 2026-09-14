# demo-gx pipeline — unified command entry points.
# Usage: make setup | data | run | test | clean

PYTHON := .venv/bin/python
ENV    ?= dev

.PHONY: setup data run test lint clean

## First run only: create the virtualenv and install the package in editable mode.
## Dependencies are declared once in pyproject.toml; there is no separate lock file.
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -e ".[dev]"

## Generate the sample input for the selected environment
## (data/$(ENV)/input/sample_data.json)
data:
	$(PYTHON) scripts/generate_sample_data.py --env $(ENV)

## Run the full pipeline (override env: ENV=test make run)
run: data
	$(PYTHON) -m demo_gx.cli --env $(ENV)

## Run the pytest suite
test:
	$(PYTHON) -m pytest tests/ -v

## Lint, format check and type check. All three read pyproject.toml.
lint:
	$(PYTHON) -m ruff check src scripts tests
	$(PYTHON) -m ruff format --check src scripts tests
	$(PYTHON) -m mypy

## Remove run artefacts. Committed sample inputs and the layer skeleton stay.
## NOTE: do not reduce this to `rm -rf data/*/output/*`. That expands to the
## layer directory names and deletes them recursively, taking the committed
## .gitkeep placeholders with it and dirtying the worktree.
clean:
	find data -type f -path '*/output/*' ! -name '.gitkeep' -delete
	find data -type d -path '*/output/*' -empty -delete
