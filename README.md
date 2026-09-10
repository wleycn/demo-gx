# Pipeline Project

## Quick Start

Prerequisites: Python 3.10+ and `make` (Linux/macOS). Every step has a
`make` target; the manual equivalents are listed below for environments
without `make`.

| # | Command | What it does |
|---|---------|--------------|
| 1 | `make setup` | First run only: create `.venv` and install dependencies |
| 2 | `make data` | Generate `data/sample_data.json` (107 records incl. injected anomalies) |
| 3 | `make run` | Run the pipeline (default env `dev`; override: `ENV=test make run`) |
| 4 | `make test` | Run the pytest suite |
| 5 | `make clean` | Remove ALL run artifacts (`data/`, `test/data/`, `data_prod/` — samples/metrics/logs live inside) for a clean re-run |

Manual equivalents (no `make`):

```bash
# 1. Setup (first run only)
python3 -m venv .venv
# activate venv (option)
source .venv/bin/activate
.venv/bin/pip install -r requirements.txt
# 2. Generate data
.venv/bin/python scripts/generate_sample_data.py
# 3. Run the pipeline
.venv/bin/python pipeline/cli.py --input data/sample_data.json --env dev
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

## Repository Layout

```text
demo-gx/
├── pipeline/                 # Python packages (namespace packages, no __init__.py)
│   ├── cli.py                # Entry point: orchestrates read → Bronze → validate → clean → dedup → Silver → Gold
│   ├── ingestion/reader.py   # read_input() + write_bronze()
│   ├── validation/schema_validator.py   # SchemaValidator (strict contract validation)
│   ├── transformation/cleaner.py        # DataCleaner
│   ├── transformation/deduplicator.py   # Deduplicator
│   ├── curation/builder.py              # GoldBuilder (fact / dims / wide)
│   └── common/               # config.py, logger.py, metrics.py
├── config/                   # dev.yaml / test.yaml / prod.yaml + schema.yaml (data contract)
├── docs/                     # architecture.md, data-design.md, module-design.md, requirements.md, raw/
├── tests/test_validation.py # pytest contract edge-case suite
├── scripts/generate_sample_data.py
├── Makefile                  # setup / data / run / test / clean
├── .gitlab-ci.yml            # CI skeleton (test → data-quality → promote)
├── .gitattributes            # line-ending policy (md=CRLF, code=LF)
├── requirements.txt
└── README.md
```

Run artifacts (sample input, Bronze/Silver/Gold, metrics, logs) live under
the environment storage dirs (`data/`, `test/data/`, `data_prod/`) and are git-ignored.



## git repo:
https://github.com/wleycn/demo-gx
