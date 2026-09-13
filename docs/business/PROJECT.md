# Project Overview

A Pandas-based single-machine lakehouse reference implementation for the Principal Data
Engineer (P5) take-home assessment. It processes JSON event data through a three-layer
pipeline: Bronze (raw archive) to Silver (cleaned detail) to Gold (curated star schema).

## Design Goals

- A **reusable, extensible** reference implementation that supports file, API, database, and
  event-stream source systems.
- **dev to test to prod** environment promotion driven by configuration switching.
- **Production-minded**: quality checks, error isolation, auditing, and cost awareness.

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

The target production shape is Spark on Iceberg; this repo develops and validates locally on
Pandas because no big-data cluster is available. KNOWN-ISSUE.md holds the decision record
and the full list of deviations from the production shape.

## Directory Layout

```text
demo-gx/
├── src/demo_gx/              # Installable package (per-package __init__.py)
│   ├── cli.py                # Entry point: orchestrates the full ETL flow
│   ├── ingestion/reader.py   # read_input() + write_bronze()
│   ├── validation/schema_validator.py   # SchemaValidator (strict contract validation)
│   ├── validation/error_envelope.py     # Quarantine envelope build + write
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
├── pyproject.toml            # Single entry for dependencies, packaging and pytest config
├── .gitlab-ci.yml            # CI skeleton (test -> data-quality -> promote)
├── .gitattributes            # Line-ending policy (md=CRLF, code=LF)
└── README.md
```

The package is installed in editable mode by `make setup`, so the entry point is
`python -m demo_gx.cli`. Run artifacts (sample input, Bronze/Silver/Gold, metrics, logs) live
under environment storage dirs (`data/`, `test/data/`, `data_prod/`) and are git-ignored.

## Contract Summary

- **Data contract**: `config/schema.yaml` defines 8 required fields with types, enum values,
  regex patterns, and minimum values. Strict mode rejects unknown fields.
- **Environment config**: `config/{dev,test,prod}.yaml` controls storage paths, logging,
  metrics, and alert endpoints. Each environment writes to its own directory: dev to
  `data/`, test to `test/data/`, prod to `data_prod/`.
- **AI constraints**: `AGENTS.md` at the project root defines red lines and behavior rules
  for AI coding tools.

## Security and Privacy

- **Sensitive fields** such as `customer_id` can be configured for masking or hashing. The
  mask is applied at the Silver layer, so Gold never holds the raw value.
- **Credentials** come from environment variables or a secret manager (for example Vault).
  They never appear in code, config files, or logs.
- **Audit records**: each run records its input source, output paths, and row counts, so a
  past run can be reconstructed.

## Cost and Storage Lifecycle

- **Query pruning**: the Silver layer is partitioned by `event_date`, so a query reads only
  the partitions it needs.
- **Cheaper downstream compute**: Gold exposes aggregations and a denormalized wide table,
  so BI and ML jobs do not rescan detail data.
- **Storage lifecycle**: Bronze is retained for 30 days, Silver permanently, Gold on demand.
- **Single-machine fit**: Pandas keeps the demo runnable inside the stated volume assumption
  of under 10 GB per batch.

## Verification Commands

```bash
# Run the pipeline
make run
# Run tests
make test
# Or manually
.venv/bin/python -m demo_gx.cli --input data/sample_data.json --env dev
.venv/bin/python -m pytest tests/ -q
```

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
| `#coverage-gate-off` | No coverage gate; baseline is one assertion per requirement |
| `#no-catalog` | No catalog; local Parquet without session management |
| `#no-snapshot-lifecycle` | No snapshot layer; partition directories are overwritten directly |
| `#amount-float` | `amount` column uses `float64` instead of `DECIMAL` |
| `#table-contract-approval` | No approval chain for table contracts |
| `#clock-reads-outside-data-stamping` | Telemetry modules still read the clock; no data-stamping site does |

Resolved migration items are listed under "Resolved Migration Items" in [KNOWN-ISSUE.md](KNOWN-ISSUE.md).

## Future Extensions

- Migrate from Pandas to PySpark for larger data volumes.
- Introduce Great Expectations or dbt for data contract validation.
- Adopt Apache Iceberg for schema evolution and time travel. Iceberg DDL assets are prepared
  in `docs/archive/data-design.md` section 6.
- Add stream processing (Kafka plus Spark Structured Streaming or Flink).
- Integrate OpenLineage for lineage tracking.
- Use Airflow for orchestration and scheduling.
