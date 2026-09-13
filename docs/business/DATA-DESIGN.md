# Data Flow and Data Structure Design

## 1. End-to-End Data Flow

The pipeline reads a JSON file and distributes each record through three layers. Invalid records are quarantined at the validation gate and never reach Silver or Gold.

| Layer | Name | Storage format | Consumer | Description |
|---|---|---|---|---|
| Bronze | Raw archive | JSON Lines, partitioned by `source_system/dt` | Data engineers, audit | Immutable landing zone, full lineage |
| Silver | Cleaned detail | Parquet, partitioned by `event_date` | Data scientists, analysts | Validated, deduplicated, standardized rows |
| Gold | Curated | Parquet, partitioned by `event_date`, plus full-snapshot dimensions | BI reports, ML features | Subject-oriented aggregation and dimensional model |

```text
[Input file (JSON/CSV/Parquet)]
  |
  | ingestion.read_input()
  v
[Append _raw_json column]          <-- preserve original row for audit
  |
  v
[ingestion.write_bronze()]         <-- archive full batch to Bronze (JSON Lines)
  |                                    partitioned by source_system + ingestion date
  |  --event-date (optional) scopes processing to one date
  |     Bronze always keeps the full batch
  v
[SchemaValidator.validate()]       <-- strict validation of 8 required fields
  |                                    rejects extra fields
  +----------+----------+
  | Pass     | Fail
  v          v
[valid_df]  [errors/bad_schema/]   <-- JSON Lines with error envelope
  |          (pipeline continues processing valid data)
  v
[DataCleaner]                      <-- timestamp UTC standardization
  |                                    currency normalization (invalid -> USD + flag)
  |                                    amount numeric coercion + backup
  v
[Deduplicator.deduplicate()]       <-- deduplicate by event_id
  |                                    keep latest ingestion_timestamp
  |                                    superseded rows -> duplicates.log
  v
[Write Silver (Parquet)]           <-- partition by event_date
  |                                    overwrite per partition (idempotent)
  |                                    _processed_timestamp added at write time
  v
[GoldBuilder]                      <-- reads full on-disk Silver snapshot
  |
  +--------+--------+--------+
  |        |        |
  v        v        v
[fact_     [dim_      [wide_
 daily_     customer   daily_
 events]    dim_       user_
            event_     events]
            type]
(partitioned)  (full snapshot)  (partitioned)
```

### Key Flow Branches

**Bad data path**: Records that fail validation (missing required fields, type mismatch, extra fields, future timestamp) are quarantined to `errors/bad_schema/` with an error envelope. The pipeline continues processing valid data without interruption.
**Type change path**: Type and format violations (non-numeric amount, timestamp parse failures) are quarantined at the validation stage together with schema violations. They do not reach Silver. The validator's error reason distinguishes them with `error_type=type_coercion_failed`. A separate "flag and pass to Silver" path is not enabled; the decision and its rationale are recorded in KNOWN-ISSUE.md under "Fail-safe isolation over flag-and-pass".
**Deduplication path**: For duplicate `event_id` values, only the record with the latest `ingestion_timestamp` is kept. On an exact tie (identical `ingestion_timestamp`), the last-occurring row in the input file wins (keep-last; stable sort). Superseded duplicates are written to `errors/duplicates.log` for post-hoc review.
**Backfill path**: When `--event-date YYYY-MM-DD` is given, only rows whose `event_timestamp` falls on that date are processed. Rows whose timestamp does not parse are kept in scope so the validator can quarantine them. Bronze always archives the full arriving batch. Gold is rebuilt from the full on-disk Silver snapshot; section 2.4 explains why that makes a partial run safe.

## 2. Data Structure Definitions

### 2.1 Storage Layout

Environment-isolated directory structure. The root comes from the `storage.base_path` config setting; INTERFACE-DESIGN.md section 3.1 lists the root for each environment.

```text
{storage.base_path}/
├── bronze/                        # Raw JSON archive (immutable)
│   └── {source_system}/
│       └── dt={YYYY-MM-DD}/
│           └── events.json
├── silver/                        # Cleaned detail layer (Parquet)
│   └── event_date={YYYY-MM-DD}/
│       └── data.parquet
├── gold/                          # Aggregation/dimension layer (Parquet)
│   ├── fact_daily_events/
│   │   └── event_date={YYYY-MM-DD}/
│   │       └── data.parquet
│   ├── dim_customer/
│   │   └── data.parquet           # Full snapshot, non-partitioned
│   ├── dim_event_type/
│   │   └── data.parquet
│   └── wide_daily_user_events/
│       └── event_date={YYYY-MM-DD}/
│           └── data.parquet
├── errors/
│   ├── bad_schema/
│   │   └── {timestamp}_errors.json
│   └── duplicates.log             # Plain text, appended
├── metrics.json
└── logs/
    └── pipeline.log
```

### 2.2 Bronze Layer (Raw JSON Lines)

**Storage**: one `events.json` per partition. JSON Lines format, one raw event per line. Archived as ingested: no cleaning, no quality judgement. Values keep their JSON types (pandas round-trips a JSON integer like `10` as `10.0`). Rows that are later quarantined at the Silver gate are still present here.
**Partition keys**: `source_system` (top-level directory) plus `dt` (ingestion date derived from `ingestion_timestamp`). Missing source or timestamp falls back to `unknown` and the run date respectively.
**Idempotency**: partition-scoped overwrite. Re-running the same batch rewrites the same `events.json` for each partition. A production Bronze would append new files instead.

| Field | Type | Description | Constraint |
|---|---|---|---|
| `event_id` | string | Unique event ID | UUID v4 format |
| `source_system` | string | Source system (partition key) | Any raw value; no enum check at this layer |
| `customer_id` | string | Customer ID | None |
| `event_type` | string | Event type | None |
| `event_timestamp` | string | Event time (ISO-8601, raw) | Kept as original string |
| `amount` | number | Amount (original) | May be invalid; not yet validated |
| `currency` | string | Currency code (original) | May be invalid; not yet normalized |
| `ingestion_timestamp` | string | Ingestion time (ISO-8601, raw) | Source of the `dt` partition key |

### 2.3 Silver Layer (Cleaned Parquet)

**Partition key**: `event_date` (the date extracted from `event_timestamp`, typed as `date`).
**Idempotency**: file-level overwrite per date partition. Each partition's `data.parquet` is rewritten per run. Empty partitions from earlier batches are not pruned. A full clean re-run (`make clean`) removes all artifacts.
**Deduplication**: by `event_id`, keeping the latest `ingestion_timestamp`.
Detailed schema and per-table contract: see [../tables/silver_events.md](../tables/silver_events.md).

### 2.4 Gold Layer (Star Schema)

The Gold layer adopts a star schema with one fact table, two dimension tables, and one denormalized wide table.

| Table | Type | Partition | Grain | Contract |
|---|---|---|---|---|
| `fact_daily_events` | Fact | `event_date` | per day per customer per event type | [../tables/fact_daily_events.md](../tables/fact_daily_events.md) |
| `dim_customer` | Dimension | none (full snapshot) | one row per customer | [../tables/dim_customer.md](../tables/dim_customer.md) |
| `dim_event_type` | Dimension | none (full snapshot) | one row per event type | [../tables/dim_event_type.md](../tables/dim_event_type.md) |
| `wide_daily_user_events` | Wide | `event_date` | same as fact, denormalized | [../tables/wide_daily_user_events.md](../tables/wide_daily_user_events.md) |

Gold is always rebuilt from the full on-disk Silver snapshot, never from the in-memory batch. This ensures that dimension tables and the wide table are full snapshots, so a backfill run for one date does not lose rows or shrink dimensions.

### 2.5 Error Records

Errors are written to `errors/bad_schema/` as JSON Lines, one error object per line. The envelope fields are an output contract; the field table lives in INTERFACE-DESIGN.md section 4.

### 2.6 Reprocessing Semantics

- **Batch window**: the pipeline processes the full input batch and distributes rows to Silver partitions by their `event_timestamp` date. There is no default "previous day" filter. `--event-date` is the only single-day scoping mechanism.
- **Late data**: if a record's `event_timestamp` belongs to a past date, the pipeline writes it to the corresponding historical partition. Bronze retains the original JSON for replay at any time.
- **Safe backfill**: `--event-date` reprocesses only one date. Bronze archives the full arriving batch. Gold is rebuilt from the full Silver snapshot; section 2.4 explains why a partial run stays safe.

### 2.7 Production Table Format Reference (Apache Iceberg)

The Bronze/Silver/Gold layouts above are directory and file layouts that the single-machine demo writes today. In the target big-data environment, the same layers would be managed as Iceberg tables: data files remain Parquet, but a catalog plus metadata layer adds ACID transactions, partition evolution, snapshot isolation, and time travel.
Prepared Iceberg DDL assets (Spark SQL dialect) are available in the archived `docs/archive/data-design.md` section 6. These document the target shape and are ready to run once a big-data environment is available. They are not executable in this repository's current environment.
The mapping between demo and production equivalents:

| Demo (this repo, Pandas) | Production equivalent (Iceberg/Spark) |
|---|---|
| `data/bronze/{source}/dt=.../events.json` | `bronze.events` table, append-only, 30-day retention |
| `data/silver/event_date=.../data.parquet` | `silver.events` table, `DELETE+INSERT` / `MERGE INTO` |
| `data/gold/fact_daily_events/...` | `gold.fact_daily_events` table, `INSERT OVERWRITE` |
| Partition-overwrite (idempotency) | Iceberg transactions plus snapshot isolation |
| `_raw_json` audit column | Full Bronze replay via snapshot and time travel |

### 2.8 Schema Evolution

- **New fields**: pass through to Silver and Gold automatically. They do not block the pipeline and are only marked as new in metadata.
- **Type changes**: type and format violations are quarantined at the validation gate (`not numeric`, parse failure) and logged as warnings. The Slack alert is reserved, not wired.
- **Field deprecation**: a deprecated field is retained for 90 days and then removed from Gold. The Silver layer keeps the original field permanently.

## 3. Lineage and Freshness

- **Lineage**: each record's path from Bronze to Silver to Gold is traceable via `_processed_timestamp` and partition keys. OpenLineage integration is a future extension.
- **Data freshness monitoring**: in the orchestration layer (for example Airflow), a sensor can compare the latest Silver partition's `event_date` with the current date. A delay beyond a configured threshold raises an alert.

Run metrics and the log format are output contracts. See INTERFACE-DESIGN.md sections 5 and 3.6.
