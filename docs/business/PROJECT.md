# Project Overview

A Pandas-based single-machine lakehouse reference implementation for the Principal Data Engineer (P5) take-home assessment. It processes JSON event data through a three-layer pipeline: Bronze (raw archive) to Silver (cleaned detail) to Gold (curated star schema).

## Technology Stack

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.11 (minimum 3.10) | Required by the assignment; rich data ecosystem |
| Data engine | Pandas (single machine) | Data volume assumption < 10 GB per batch; lightweight and fast |
| Table format | Parquet (partitioned directories) | Columnar, high compression, analytics-friendly |
| Config | YAML (environment-specific) | Sensitive values injected via environment variables |
| Testing | pytest | 27 tests, all passing |
| CI | GitLab CI (`.gitlab-ci.yml`) | Required by the assignment |
| Orchestration | Makefile + CLI; Airflow blueprint only | No runnable DAG in this repo |

The target production shape is Spark on Iceberg. This repo develops and validates locally on Pandas because no big-data cluster is available. Module boundaries communicate through DataFrame contracts (no global state, no file-path coupling), so each stage can be re-implemented against `pyspark.sql.DataFrame` without re-architecting the pipeline. See KNOWN-ISSUE for the full list of deviations from the production shape.

## Directory Layout

```text
demo-gx/
├── pipeline/                 # Python packages (namespace packages, no __init__.py)
│   ├── cli.py                # Entry point: orchestrates the full ETL flow
│   ├── ingestion/reader.py   # read_input() + write_bronze()
│   ├── validation/schema_validator.py   # SchemaValidator (strict contract validation)
│   ├── transformation/cleaner.py        # DataCleaner
│   ├── transformation/deduplicator.py   # Deduplicator
│   ├── curation/builder.py              # GoldBuilder (fact / dims / wide)
│   └── common/               # config.py, logger.py, metrics.py, time_utils.py
├── config/                   # dev.yaml / test.yaml / prod.yaml + schema.yaml (data contract)
├── docs/
│   ├── business/             # Seven business documents (this directory)
│   ├── tables/               # Per-table contracts (one file per table)
│   ├── changes/              # Per-module change logs
│   ├── rules/                # Engineering rules (structure / coding / flow / acceptance)
│   └── archive/              # Superseded documents (architecture / data-design / module-design / requirements / change-logs / known-issues) + raw/ (original prompt)
├── tests/                    # pytest suite (27 tests)
├── scripts/generate_sample_data.py
├── Makefile                  # setup / data / run / test / clean
├── .gitlab-ci.yml            # CI skeleton (test -> data-quality -> promote)
├── .gitattributes            # Line-ending policy (md=CRLF, code=LF)
├── requirements.txt
└── README.md
```

Run artifacts (sample input, Bronze/Silver/Gold, metrics, logs) live under environment storage dirs (`data/`, `test/data/`, `data_prod/`) and are git-ignored.

## Contract Summary

- **Data contract**: `config/schema.yaml` defines 8 required fields with types, enum values, regex patterns, and minimum values. Strict mode rejects unknown fields.
- **Environment config**: `config/{dev,test,prod}.yaml` controls storage paths, logging, metrics, and alert endpoints. Each environment writes to its own directory: dev to `data/`, test to `test/data/`, prod to `data_prod/`.
- **AI constraints**: `AGENTS.md` at the project root defines red lines and behavior rules for AI coding tools.

## Verification Commands

```bash
# Run the pipeline
make run
# Run tests
make test
# Or manually
.venv/bin/python pipeline/cli.py --input data/sample_data.json --env dev
.venv/bin/python -m pytest tests/ -q
```

## Pre-commit Gate

The gate script lives in the shared toolchain, so the hook is installed once per clone:

```bash
mkdir -p .git/hooks && cp scripts/hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

The gate blocks a commit when any of these three checks fails:

- credential scan
- test suite
- `AGENTS.md` structure check

The test command uses the project venv (`.venv/bin/python -m pytest -q`), so no external interpreter is required.
The hook source lives in `scripts/hooks/pre-commit`, which keeps it reviewable and reproducible.

## Document Navigation

| Document | What it covers |
|---|---|
| [README.md](../README.md) | Quick start: what this is, how to set up, how to run |
| [DATA-DESIGN.md](DATA-DESIGN.md) | End-to-end data flow, layer schemas, partitioning, reprocessing |
| [MODULE-DESIGN.md](MODULE-DESIGN.md) | Module responsibilities, interface contracts, dependencies |
| [INTERFACE-DESIGN.md](INTERFACE-DESIGN.md) | CLI parameters, input formats, output paths, error envelope, metrics |
| [DOMAIN-LANGUAGE.md](DOMAIN-LANGUAGE.md) | Project glossary |
| [CHANGELOG.md](CHANGELOG.md) | Version-level changes in reverse chronological order |
| [KNOWN-ISSUE.md](KNOWN-ISSUE.md) | Known pitfalls, design decisions, and rejected alternatives |

## Known Issues Index

The following known issues are documented in [KNOWN-ISSUE.md](KNOWN-ISSUE.md):

| Anchor | One-line summary |
|---|---|
| `#layout-flat-pipeline` | Flat namespace packages instead of installable `src/` layout |
| `#coverage-gate-off` | No coverage gate; baseline is one assertion per requirement |
| `#no-catalog` | No catalog; local Parquet without session management |
| `#no-snapshot-lifecycle` | No snapshot layer; partition directories are overwritten directly |
| `#amount-float` | `amount` column uses `float64` instead of `DECIMAL` |
| `#now-timestamp` | CLI uses `pd.Timestamp.now` for processing timestamps |
| `#cli-holds-transform` | CLI builds the error envelope instead of delegating to a module |
| `#table-contract-approval` | No approval chain for table contracts |

## Future Extensions

- Migrate from Pandas to PySpark for larger data volumes.
- Introduce Great Expectations or dbt for data contract validation.
- Adopt Apache Iceberg for schema evolution and time travel. Iceberg DDL assets are prepared in `docs/archive/data-design.md` section 6.
- Add stream processing (Kafka plus Spark Structured Streaming or Flink).
- Integrate OpenLineage for lineage tracking.
- Use Airflow for orchestration and scheduling.
