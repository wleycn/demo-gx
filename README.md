# Pipeline Project

## Quick Start

Prerequisites: Python 3.10+ and `make` (Linux/macOS). Every step has a
`make` target; the manual equivalents are listed below for environments
without `make`.

| # | Command | What it does |
|---|---------|--------------|
| 1 | `make setup` | First run only: create `.venv` and install dependencies |
| 2 | `make data` | Generate `sample_data.json` (106 records incl. injected anomalies) |
| 3 | `make run` | Run the pipeline (default env `dev`; override: `ENV=test make run`) |
| 4 | `make test` | Run the pytest suite |
| 5 | `make clean` | Remove run artifacts (`data/`, `logs/`, `metrics.json`, `sample_data.json`) for a clean re-run |

Manual equivalents (no `make`):

```bash
# 1. Setup (first run only)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 2. Generate data
.venv/bin/python scripts/generate_sample_data.py
# 3. Run the pipeline
.venv/bin/python pipeline/cli.py --input sample_data.json --env dev
# 4. Run tests
.venv/bin/python -m pytest tests/
```

## Design Notes

See the `docs/` directory for details.

## Trade-offs

- Uses Pandas for single-machine processing, suitable for <10GB data.
- Partition overwrite writes ensure idempotency.
- Strict mode rejects unknown fields to maintain data contracts.
- Runtime constraint: the target production shape is a big-data framework
  (Spark + Iceberg); this repo is validated locally on Pandas because no
  cluster environment is available. Design & Iceberg SQL assets reflect the
  big-data shape — see docs/architecture.md §5 and docs/data-design.md §6.

## Production Readiness Improvement Plan

- Migrate to PySpark for larger data volumes.
- Integrate Great Expectations for data quality validation.
- Use Airflow for orchestration and scheduling.
- Add OpenLineage for lineage tracking.

---
All code and configuration files are now provided. Save the above content
to the corresponding files. Ensure the directory structure is as follows:

```text
project_root/
├── pipeline/
│   ├── __init__.py
│   ├── cli.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── reader.py
│   ├── validation/
│   │   ├── __init__.py
│   │   └── schema_validator.py
│   ├── transformation/
│   │   ├── __init__.py
│   │   ├── cleaner.py
│   │   └── deduplicator.py
│   ├── curation/
│   │   ├── __init__.py
│   │   └── builder.py
│   └── common/
│       ├── __init__.py
│       ├── config.py
│       ├── logger.py
│       └── metrics.py
├── config/
│   ├── dev.yaml
│   ├── test.yaml
│   ├── prod.yaml
│   └── schema.yaml
├── tests/
│   ├── __init__.py
│   └── test_validation.py
├── scripts/
│   └── generate_sample_data.py
├── requirements.txt
└── README.md
```

git repo:
https://github.com/wleycn/demo-gx
