# demo-gx pipeline — unified command entry points.
# Usage: make setup | data | run | test | lint | check-data | show-data | clean

PYTHON := .venv/bin/python
ENV    ?= dev
# check-data and show-data selectors:
#   LAYER=all|bronze|silver|gold|errors, TABLE=<name>, DATE=YYYY-MM-DD
LAYER  ?= all
TABLE  ?=
DATE   ?=
# show-data only: LIMIT=<rows or lines>, COLUMNS=a,b, FORMAT=table|json|csv, SCHEMA=1
LIMIT  ?= 10
COLUMNS ?=
FORMAT ?= table
SCHEMA ?=

.PHONY: setup data run test lint check-data show-data clean

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

## Inspect what a run actually wrote, and compare it with docs/tables/*.md.
## Read-only: nothing under data/ is written. Exit 3 means nothing was scanned.
##   make check-data                          every layer, every table
##   make check-data LAYER=gold               one layer
##   make check-data LAYER=gold TABLE=fact_daily_events
##   make check-data DATE=2026-09-01          one partition only
check-data:
	$(PYTHON) scripts/check_data.py --env $(ENV) --layer $(LAYER) --table "$(TABLE)" $(if $(DATE),--event-date $(DATE),)

## Show the rows a run actually wrote. Read-only, and never a failing gate:
## a table that breaks its contract is exactly the table you want to look at.
##   make show-data                                     every layer, 10 rows each
##   make show-data LAYER=gold TABLE=fact_daily_events LIMIT=5
##   make show-data LAYER=gold TABLE=dim_customer SCHEMA=1
##   make show-data LAYER=gold TABLE=fact_daily_events COLUMNS=event_date,total_amount
##   make show-data LAYER=gold TABLE=fact_daily_events FORMAT=json   (rows on stdout)
## The recipe is silent (`@`) because FORMAT=json|csv puts rows on stdout: an
## echoed command line would land in the pipe. The tool prints its own header.
show-data:
	@$(PYTHON) scripts/show_data.py --env $(ENV) --layer $(LAYER) --table "$(TABLE)" --limit $(LIMIT) \
		--format $(FORMAT) $(if $(DATE),--event-date $(DATE),) \
		$(if $(COLUMNS),--columns "$(COLUMNS)",) $(if $(SCHEMA),--schema,)

## Remove run artefacts. Committed sample inputs and the layer skeleton stay.
## NOTE: do not reduce this to `rm -rf data/*/output/*`. That expands to the
## layer directory names and deletes them recursively, taking the committed
## .gitkeep placeholders with it and dirtying the worktree.
clean:
	find data -type f -path '*/output/*' ! -name '.gitkeep' -delete
	find data -type d -path '*/output/*' -empty -delete
