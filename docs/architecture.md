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
| source_system      | string            | Enum [web, mobile, api]                | Invalid value → quarantine + alert       |
| customer_id        | string            | Non-null string                        | Missing → quarantine                     |
| event_type         | string            | Non-null, length ≤ 64                  | Too long/null → quarantine               |
| event_timestamp    | string (ISO8601)  | Parseable as UTC, ≤ current time       | Parse failure/future time → quarantine   |
| amount             | number            | ≥ 0, precision ≤ 2 decimal places      | Negative/out of range → quarantine       |
| currency           | string            | ISO 4217 three-letter code             | Invalid code → default USD + flag        |
| ingestion_timestamp| string (ISO8601)  | Parseable as UTC, ≤ current time       | Parse failure/future time → quarantine   |


## 4. Data Flow

[Input file] → ingestion.read()
↓
validation.validate_schema() → failed records written to errors/ and alerted
↓
transformation.clean() → fill missing, standardize formats
transformation.deduplicate() → deduplicate by event_id, keep newest
↓
Write to Silver (Parquet) → partition by event_date
↓
curation.build_gold() → generate daily aggregation (total amount, event count) and wide table
↓
Write to Gold (Parquet) → for downstream queries

### Schema Evolution Compatibility
- **New fields**: automatically pass through to Silver/Gold, do not block the pipeline, only marked as "new" in metadata
- **Type changes**: trigger WARNING log + Slack alert, but preserve original value in `_raw_<field>` column, ensuring downstream is not interrupted
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
| Orchestration | Airflow (pseudo-code blueprint provided) | Industry standard, supports dependencies/retry/backfill                            |
| CI/CD         | GitLab CI (.gitlab-ci.yml skeleton provided) | Required by the assignment                                                          |

### Dimensional Modeling Strategy
The Gold layer adopts a Star Schema to support domain data product delivery:

- **Fact Table**: `fact_daily_events`
  Grain: per day per user per event type; measures: event_count, total_amount, avg_amount
- **Dimension Tables**:
  - `dim_customer`: user_id, first_seen_date, lifetime_value_segment
  - `dim_event_type`: event_type, category, business_owner
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
  - Single-machine pandas processing controls memory usage (chunked reading of large files).

## 8. Observability

- Structured logging (JSON format), recording processing time, row count, error count.
- Output statistics (total rows, passed, failed, deduplicated) to `metrics.json`.
- Future integration with OpenLineage for lineage tracking.

## 9. Environment Promotion and CI/CD Adaptation

- Switch configuration files via the `--env` parameter (`config/dev.yaml`, `test.yaml`, `prod.yaml`).
- CI pipeline stages: lint → unit tests → data quality tests → build → deploy to dev, with manual approval before promotion to test/prod.
- During deployment, only code and configuration are updated; data storage paths are isolated by environment (e.g. `s3://bucket/dev/silver/`).


## 10. Future Extension Paths

- Migrate from Pandas to PySpark for larger data volumes.
- Introduce Great Expectations or dbt for data contract validation.
- Adopt Apache Iceberg for schema evolution and time travel.
- Add stream processing (e.g. Kafka + Spark Structured Streaming).
