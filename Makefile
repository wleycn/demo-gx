# demo-gx pipeline — unified command entry points.
# Usage: make setup | data | run | test | clean

PYTHON := .venv/bin/python
INPUT  := sample_data.json
ENV    ?= dev

.PHONY: setup data run test clean

## First run only: create the virtualenv and install dependencies
setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

## Generate sample input data (sample_data.json)
data:
	$(PYTHON) scripts/generate_sample_data.py

## Run the full pipeline (override env: ENV=test make run)
run:
	$(PYTHON) pipeline/cli.py --input $(INPUT) --env $(ENV)

## Run the pytest suite
test:
	$(PYTHON) -m pytest tests/ -v

## Remove all run artifacts (data/, test/data/, data_prod/, logs/, metrics.json, sample_data.json)
clean:
	rm -rf data test/data data_prod logs metrics.json sample_data.json
