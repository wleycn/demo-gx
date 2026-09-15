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
**Type change path**: Type and format violations (non-numeric amount, timestamp parse failures) are quarantined at the validation stage together with schema violations. They do not reach Silver. The validator uses `error_type=type_coercion_failed` to distinguish them. A separate "flag and pass to Silver" path is not enabled. The decision and its rationale are recorded in KNOWN-ISSUE.md under "Fail-safe isolation over flag-and-pass".
**Deduplication path**: Silver deduplicates by `event_id`. The rule and its tie-break live in the table contract: [../tables/silver_events.md](../tables/silver_events.md).
**Backfill path**: When `--event-date YYYY-MM-DD` is given, only rows whose `event_timestamp` falls on that date are processed. Rows whose timestamp does not parse are kept in scope so the validator can quarantine them. Bronze always archives the full arriving batch. Gold is rebuilt from the full on-disk Silver snapshot. Section 2.4 explains why that makes a partial run safe.

## 2. Data Structure Definitions

### 2.1 Storage Layout

Environment-isolated directory structure. Each environment has its own root, set by the `storage.base_path` config item: `data/dev`, `data/test` and `data/prod`. The root splits into `input/` (inbound) and `output/` (what the pipeline writes). The tree below shows dev; test and prod have the same shape under their own root. Subdirectory names are the defaults of the `storage.*_subpath` config items.

```text
data/dev/output/
├── bronze/                        # Raw JSON archive (immutable)
│   └── {source_system}/           # the sample data uses api / web / mobile / unknown
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

A dev run therefore writes real paths such as `data/dev/output/bronze/web/dt=2026-09-14/events.json`, `data/dev/output/silver/event_date=2026-09-14/data.parquet` and `data/dev/output/gold/dim_customer/data.parquet`.

### 2.2 Bronze Layer (Raw JSON Lines)

**Storage**: one `events.json` per partition in JSON Lines format, one raw event per line. Archived as ingested, with one exception: configured identifiers are already masked at the ingestion boundary. No cleaning and no quality judgement otherwise. Values keep their JSON types (pandas round-trips a JSON integer like `10` as `10.0`). Rows that are later quarantined at the Silver gate are still present here.
**Partition keys**: `source_system` (top-level directory) plus `dt` (ingestion date derived from `ingestion_timestamp`). Missing source or timestamp falls back to `unknown` and the run date respectively.
**Idempotency**: partition-scoped overwrite. Re-running the same batch rewrites the same `events.json` for each partition. A production Bronze would append new files instead.

| Field | Type | Description | Constraint |
|---|---|---|---|
| `event_id` | string | Unique event ID | UUID v4 format |
| `source_system` | string | Source system (partition key) | Any raw value; no enum check at this layer |
| `customer_id` | string | Customer ID, masked at the ingestion boundary | Keyed digest of the form `h_` plus 16 hex characters |
| `event_type` | string | Event type | None |
| `event_timestamp` | string | Event time (ISO-8601, raw) | Kept as original string |
| `amount` | number | Amount (original) | May be invalid; not yet validated |
| `currency` | string | Currency code (original) | May be invalid; not yet normalized |
| `ingestion_timestamp` | string | Ingestion time (ISO-8601, raw) | Source of the `dt` partition key |

### 2.3 Silver Layer (Cleaned Parquet)

**Partition key**: `event_date` (the date extracted from `event_timestamp`, typed as `date`).
Write mode, empty-partition handling, the deduplication rule, and the column contract live in the table contract: see [../tables/silver_events.md](../tables/silver_events.md).

### 2.4 Gold Layer (Star Schema)

The Gold layer adopts a star schema with one fact table, two dimension tables, and one denormalized wide table.

Partition, grain, and business key for each table live in its own contract.

| Table | Type | Contract |
|---|---|---|
| `fact_daily_events` | Fact | [../tables/fact_daily_events.md](../tables/fact_daily_events.md) |
| `dim_customer` | Dimension | [../tables/dim_customer.md](../tables/dim_customer.md) |
| `dim_event_type` | Dimension | [../tables/dim_event_type.md](../tables/dim_event_type.md) |
| `wide_daily_user_events` | Wide | [../tables/wide_daily_user_events.md](../tables/wide_daily_user_events.md) |

Gold is always rebuilt from the full on-disk Silver snapshot, never from the in-memory batch. This ensures that dimension tables and the wide table are full snapshots. A backfill run for one date does not lose rows or shrink dimensions.

### 2.5 Error Records

Errors are written to `errors/bad_schema/` as JSON Lines, one error object per line. The envelope fields are an output contract; the field table lives in INTERFACE-DESIGN.md section 4.

### 2.6 Reprocessing Semantics

- **Batch window**: the pipeline processes the full input batch and distributes rows to Silver partitions by their `event_timestamp` date. There is no default "previous day" filter. `--event-date` is the only single-day scoping mechanism.
- **Late data**: if a record's `event_timestamp` belongs to a past date, the pipeline writes it to the corresponding historical partition. Bronze retains the original JSON for replay at any time.
- **Safe backfill**: `--event-date` reprocesses only one date. Bronze archives the full arriving batch. Gold is rebuilt from the full Silver snapshot. Section 2.4 explains why a partial run stays safe.

### 2.7 Production Table Format Reference (Apache Iceberg)

The Bronze/Silver/Gold layouts above are directory and file layouts that the single-machine demo writes today. In the target big-data environment the same layers would be managed as Iceberg tables. Data files remain Parquet, but a catalog plus metadata layer adds ACID transactions, partition evolution, snapshot isolation, and time travel.
The DDL below is a prepared production asset, in Spark SQL plus Iceberg dialect. It is not executable in this repository's current environment, which has no Spark, no Iceberg runtime and no catalog. It documents the target shape and is ready to run once a big-data environment exists.
The mapping between demo and production equivalents. Paths start at the environment's `output/` root, which is `data/dev/output/` in dev:

| Demo (this repo, Pandas) | Production equivalent (Iceberg/Spark) |
|---|---|
| `bronze/{source}/dt=.../events.json` | `bronze.events` table, append-only, 30-day retention |
| `silver/event_date=.../data.parquet` | `silver.events` table, `DELETE+INSERT` / `MERGE INTO` |
| `gold/fact_daily_events/...` | `gold.fact_daily_events` table, `INSERT OVERWRITE` |
| Partition-overwrite (idempotency) | Iceberg transactions plus snapshot isolation |
| `_raw_json` audit column | Full Bronze replay via snapshot and time travel |

#### Bronze: raw archive, append-only and immutable

```sql
-- Catalog: HadoopCatalog pointed at a warehouse directory
CREATE DATABASE IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.events (
    event_id            STRING,
    source_system       STRING,
    customer_id         STRING,
    event_type          STRING,
    event_timestamp     TIMESTAMP,
    amount              DECIMAL(18,2),
    currency            STRING,
    ingestion_timestamp TIMESTAMP,
    _raw_json           STRING   -- full original record for replay/audit
)
USING iceberg
PARTITIONED BY (source_system, days(ingestion_timestamp))
TBLPROPERTIES (
    'format-version' = '2',
    'write.format.default' = 'parquet',
    'history.expire.max-snapshot-age-ms' = '2592000000'  -- 30-day Bronze retention
);

-- Append-only ingest (Bronze is immutable: never UPDATE/DELETE here)
INSERT INTO bronze.events
SELECT ... FROM source_staging_table;
```

#### Silver: cleaned detail, upsert by business key

```sql
CREATE DATABASE IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.events (
    event_id            STRING,
    source_system       STRING,
    customer_id         STRING,
    event_type          STRING,
    event_timestamp     TIMESTAMP,
    amount              DECIMAL(18,2),
    currency            STRING,
    ingestion_timestamp TIMESTAMP,
    event_date          DATE,
    _validation_status  STRING,  -- 'passed' (type_mismatch reserved, yellow path disabled)
    _raw_amount         STRING   -- original value kept on coercion failure
)
USING iceberg
PARTITIONED BY (days(event_timestamp))
TBLPROPERTIES ('format-version' = '2');

-- Deduplicated refresh of one date partition (retry-safe, ACID):
-- DELETE + INSERT inside one Iceberg transaction
DELETE FROM silver.events
WHERE event_date = '2026-09-09';

INSERT INTO silver.events
SELECT ... FROM bronze.events
WHERE days(ingestion_timestamp) = DATE '2026-09-09'
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY event_id ORDER BY ingestion_timestamp DESC
) = 1;

-- Alternative for incremental upsert (CDC-style): keep the newest record
MERGE INTO silver.events t
USING bronze.events_delta s
ON t.event_id = s.event_id
WHEN MATCHED AND s.ingestion_timestamp > t.ingestion_timestamp
    THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

#### Gold: curated star schema, idempotent partition overwrite

```sql
CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_daily_events (
    event_date   DATE,
    customer_id  STRING,
    event_type   STRING,
    event_count  BIGINT,
    total_amount DECIMAL(18,2),
    avg_amount   DECIMAL(18,2)
)
USING iceberg
PARTITIONED BY (days(event_date));

-- Partition-overwrite write (equivalent of the demo's idempotent mode)
INSERT OVERWRITE gold.fact_daily_events
SELECT event_date, customer_id, event_type,
       COUNT(*)          AS event_count,
       SUM(amount)       AS total_amount,
       AVG(amount)       AS avg_amount
FROM silver.events
WHERE event_date = DATE '2026-09-09'
GROUP BY event_date, customer_id, event_type;

-- Dimension tables (dim_customer, dim_event_type) and the denormalized
-- wide table follow the same pattern; dims use full-snapshot refresh.
```

#### Analytics reads: snapshot isolation and time travel

```sql
-- Snapshot as of a wall-clock time (consistent point-in-time read)
SELECT event_type, SUM(total_amount)
FROM gold.fact_daily_events
TIMESTAMP AS OF '2026-09-10 00:00:00'
GROUP BY event_type;

-- Explicit snapshot version
SELECT * FROM silver.events VERSION AS OF 12345678901234567;

-- Incremental consumption: only new snapshots since the last watermark
SELECT * FROM silver.events
WHERE _snapshot_id IN (
    SELECT snapshot_id FROM silver.events.snapshots
    WHERE committed_at > TIMESTAMP '2026-09-10 00:00:00'
);
```

### 2.8 Schema Evolution

- **New fields**: pass through to Silver and Gold automatically. They do not block the pipeline and are only marked as new in metadata.
- **Type changes**: type and format violations are quarantined at the validation gate (`not numeric`, parse failure) and logged as warnings. The Slack alert is reserved, not wired.
- **Field deprecation**: a deprecated field is retained for 90 days and then removed from Gold. The Silver layer keeps the original field permanently.

## 3. Lineage and Freshness

- **Lineage**: each record's path from Bronze to Silver to Gold is traceable via `_processed_timestamp` and partition keys. OpenLineage integration is a future extension.
- **Data freshness monitoring**: in the orchestration layer (for example Airflow), a sensor can compare the latest Silver partition's `event_date` with the current date. A delay beyond a configured threshold raises an alert.

Run metrics and the log format are output contracts. See INTERFACE-DESIGN.md sections 5 and 3.6.
