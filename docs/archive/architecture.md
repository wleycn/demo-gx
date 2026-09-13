# Data Pipeline Architecture Design

## 1. Design Goals

- Build a **reusable, extensible** reference implementation supporting file/API/database/event-stream source systems.
- Support **dev → test → prod** environment promotion via configuration switching.
- Emphasize **production-minded thinking**: quality checks, error isolation, auditing, cost awareness.

## 2. Overall Layering (Lakehouse Style)


| Layer   | Name           | Storage Format        | Consumer              | Description                                   |
| ------- | -------------- | --------------------- | --------------------- | --------------------------------------------- |
| Bronze  | Raw layer      | JSON / raw files      | Data engineer/audit   | Stores raw input, immutable, full lineage     |
| Silver  | Cleaned layer  | Parquet (partitioned) | Data scientist/analyst| Validated, deduplicated, standardized detail data |
| Gold    | Curated layer  | Parquet / wide tables | BI reports/ML features| Subject-oriented aggregation, dimensional modeling, data products |

## 3. Module Partitioning (Separation of Concerns)

```text
pipeline/
├── ingestion/ # Read raw data (supports JSON/CSV/Parquet)
├── validation/ # Schema validation + quality rules (null/enum/type)
├── transformation/ # Cleaning (standardize dates, currency), deduplication
├── curation/ # Build aggregation/Gold (summarize by customer/event_type)
├── common/ # Logging, config, exception handling, audit
└── cli.py # Unified entry point (supports --env dev/test/prod)
```

### Source Schema Alignment
This pipeline is designed strictly based on the JSON event template provided in the requirements document. Core fields and validation rules are as follows:

| Field              | Type              | Validation Rule                        | Error Handling                           |
|--------------------|-------------------|----------------------------------------|------------------------------------------|
| event_id           | string            | UUID v4 format, non-null               | Missing/format error → quarantine to errors/bad_schema/ |
| source_system      | string            | Enum [web, mobile, api]                | Invalid value → quarantine (alert reserved, not wired) |
| customer_id        | string            | Non-null string                        | Missing → quarantine                     |
| event_type         | string            | Non-null, length ≤ 64                  | Too long/null → quarantine               |
| event_timestamp    | string (ISO8601)  | Parseable as UTC, ≤ current time       | Parse failure/future time → quarantine   |
| amount             | number            | ≥ 0, precision ≤ 2 decimal places      | Negative/out of range → quarantine       |
| currency           | string            | Three-letter code (demo whitelist {USD, EUR, GBP, CNY, JPY}; subset of ISO 4217) | Code outside whitelist → default USD + flag        |
| ingestion_timestamp| string (ISO8601)  | Parseable as UTC, ≤ current time       | Parse failure/future time → quarantine   |


## 4. Data Flow

```text
[Input file] → ingestion.read_input()
↓
ingestion.write_bronze() → archive full arriving batch (Bronze, partitioned by source/dt)
↓
validation: SchemaValidator.validate() → valid rows continue; invalid → errors/bad_schema/ (+ alert reserved)
↓
transformation: DataCleaner (timestamps UTC, currency, amount) → Deduplicator.deduplicate() (keep newest)
↓
Write to Silver (Parquet) → partition by event_date (+ _processed_timestamp)
↓
curation: GoldBuilder → daily fact aggregation + dimensions + wide table
↓
Write to Gold (Parquet) → for downstream queries
```

### Schema Evolution Compatibility
- **New fields**: automatically pass through to Silver/Gold, do not block the pipeline, only marked as "new" in metadata
- **Type changes**: type/format violations are quarantined at validation
  (e.g. `not numeric`, parse failure); a `WARNING` is logged. Slack alert is
  **reserved, not wired**.
- **Field deprecation**: retained for 90 days then removed from Gold layer; Silver layer permanently retains the original field

## 5. Technology Selection and Trade-offs


| Component     | Choice                                 | Rationale                                                                           |
| ------------- | -------------------------------------- | ----------------------------------------------------------------------------------- |
| Language      | Python 3.10+                           | Required, rich ecosystem                                                            |
| Data processing | Pandas (can migrate to PySpark)       | Estimated data volume < 10GB; Pandas is lightweight and fast; code structure stays similar to Spark for extensibility |
| Input format  | JSON (example), extensible to CSV/Parquet | Adapts to different sources via factory pattern                                    |
| Output format | Parquet (columnar, high compression, analytics-friendly) | Balances performance and cost                                                       |
| Config management | YAML (environment-specific)        | Sensitive info injected via environment variables                                   |
| Testing       | pytest + custom data quality checks    | Meets unit test + data test requirements                                            |
| Orchestration | Airflow (blueprint in module-design §2.7; no runnable DAG in repo) | Industry standard, supports dependencies/retry/backfill                            |
| CI/CD         | GitLab CI (.gitlab-ci.yml at repo root) | Required by the assignment                                                          |

### Runtime Environment Constraint (Explicit Design Decision)

The **target production shape** of this pipeline is a big-data execution
framework (e.g. Spark on a managed cluster) over a Lakehouse table format
(e.g. Apache Iceberg) — see the Iceberg reference SQL in `docs/data-design.md`
§6. The source systems, Bronze/Silver/Gold layering, and promotion model are
all designed against that shape.

This reference implementation is nevertheless **developed and validated in a
single-machine environment without access to a big-data cluster**. That
constraint is an explicit design decision, not an accident:

- The executable engine is **Pandas on a single machine**, sized for the
  declared volume assumption (< 10 GB per batch). The pipeline runs
  end-to-end locally with `pandas` only.
- Module boundaries communicate exclusively through **DataFrame contracts**
  (no global state, no file-path coupling), so the Pandas implementation is a
  faithful stand-in for a Spark implementation — each stage can be
  re-implemented against `pyspark.sql.DataFrame` without re-architecting the
  pipeline.
- The migration surface is kept explicit (see §10); Iceberg DDL assets are
  prepared in `docs/data-design.md` §6 so the target shape is runnable the
  moment a big-data environment is available.

This mirrors a common production reality: **design and data contracts target
the big-data shape; local development and demo runs execute on a smaller
engine.**

### Dimensional Modeling Strategy
The Gold layer adopts a Star Schema to support domain data product delivery:

- **Fact Table**: `fact_daily_events`
  Grain: per day per user per event type; measures: event_count, total_amount, avg_amount
- **Dimension Tables**:
  - `dim_customer`: customer_id, first_seen_date
  - `dim_event_type`: event_type
- **Wide Table (Denormalized View)**: `wide_daily_user_events`
  Pre-joined Fact + Dimensions, for direct BI queries, reducing runtime Join overhead



## 6. Error Handling Strategy

- **Schema mismatch**: quarantine to `errors/bad_schema/`, log detailed errors, continue processing other records (does not block the batch).
- **Missing file**: fail fast (raise exception), retried by the orchestration layer.
- **Duplicate records**: keep the one with the latest `ingestion_timestamp`; log the rest to `duplicates.log`.
- **Late data**: partitioned by `event_timestamp`, supports reprocessing.

## 7. Security and Cost Control

- **Security**:
  - Sensitive fields (e.g. `customer_id`) can be configured for masking (mask or hash), applied at the Silver layer.
  - Credentials injected via environment variables or a secrets management service (e.g. Vault), never in code.
  - Audit logs record each run's input source, output path, and row count.
- **Cost**:
  - Silver layer partitioned by `event_date` for query pruning.
  - Gold layer uses aggregation and wide tables to reduce downstream compute cost.
  - Storage lifecycle configured (Bronze retained 30 days, Silver permanent, Gold on-demand).
  - Single-machine pandas processing keeps the demo runnable within the
    <10 GB volume assumption.

## 8. Observability

- Structured logging (JSON format), recording processing time, row count, error count.
- Output statistics (total rows, passed, failed, deduplicated) to `metrics.json` under the env's storage base path.
- Future integration with OpenLineage for lineage tracking.

## 9. Environment Promotion and CI/CD Adaptation

- Switch configuration files via the `--env` parameter (`config/dev.yaml`, `test.yaml`, `prod.yaml`).
- CI pipeline stages (see the `.gitlab-ci.yml` skeleton at the repo root): unit tests → data-quality end-to-end smoke → manual promote gate. Lint and build stages are not yet defined in the skeleton.
- During deployment, only code and configuration are updated; data storage paths are isolated by environment (e.g. `s3://bucket/dev/silver/`).


## 10. Future Extension Paths

- Migrate from Pandas to PySpark for larger data volumes.
- Introduce Great Expectations or dbt for data contract validation.
- Adopt Apache Iceberg for schema evolution and time travel.
- Add stream processing (e.g. Kafka + Spark Structured Streaming/Flink).
