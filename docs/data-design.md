# Data Flow and Data Structure Design

## 1. Physical Data Paths (Storage Layout)

Adopts an **environment-isolated** directory structure. Local development uses `./data` as the root directory; production can map to S3/ADLS (via configuration switching).

```text
data/
├── bronze/ # Raw JSON archive (immutable)
│ └── {source_system}/ # Subdirectory per source system
│ └── dt={YYYY-MM-DD}/ # Partitioned by ingestion date
│ └── events.json
├── silver/ # Cleaned detail layer (Parquet)
│ └── event_date={YYYY-MM-DD}/ # Partitioned by event date
│ └── data.parquet
├── gold/ # Aggregation/dimension layer (Parquet)
│ ├── fact_daily_events/
│ │ └── event_date={YYYY-MM-DD}/
│ │ └── data.parquet
│ ├── dim_customer/
│ │ └── data.parquet (full snapshot, non-partitioned)
│ ├── dim_event_type/
│ │ └── data.parquet
│ └── wide_daily_user_events/
│ └── event_date={YYYY-MM-DD}/
│ └── data.parquet
└── errors/ # Anomalous data quarantine area
├── bad_schema/ # Missing fields/extra fields/format errors
│ └── {timestamp}_errors.json
├── type_mismatch/ # (Reserved) dedicated type-conversion quarantine;
│   #   currently type failures are filed under bad_schema/ with
│   #   error_type=type_coercion_failed (see §3.4)
│ └── {timestamp}_errors.json
└── duplicates.log # Deduplication record log (plain text, appended)
```


---

## 2. Detailed Data Flow (with Exception Branches)

The diagram below shows the complete path from input to output, including the handling flow for bad data and special cases.

```text
┌─────────────┐
│ Input file  │
│ (JSON/CSV/  │
│ Parquet)    │
└──────┬──────┘
│ ingestion.read()
▼
┌─────────────────────┐
│ Append raw_json col │ ← preserve original row for audit
└──────────┬──────────┘
│
▼
┌─────────────────────────────────┐
│ validation.validate_schema()    │ ← strictly validate 8 required fields, reject extra fields
└──────────┬──────────┬───────────┘
│ │
Pass │ │ Fail
│ ▼
│ ┌─────────────────────┐
│ │ Write to errors/    │
│ │ bad_schema/         │
│ │ + send alert (opt)  │
│ └─────────────────────┘
▼
┌─────────────────────────────────┐
│ transformation.clean()          │ ← timestamp UTC standardization, currency normalization
│ Generate raw* cols (if type     │ ← set validation_status
│ conversion fails)               │
└──────────┬──────────────────────┘
│
▼
┌─────────────────────────────────┐
│ transformation.deduplicate()    │ ← deduplicate by event_id, keep latest ingestion_timestamp
│ Duplicate records written to    │
│ duplicates.log                  │
└──────────┬──────────────────────┘
│
▼
┌─────────────────────────────────┐
│ Write to Silver (Parquet)       │ ← partition by event_date, overwrite write
└──────────┬──────────────────────┘
│
├─────────────┬─────────────┐
▼ ▼ ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ curation.       │ │ curation.    │ │ curation.        │
│ build_fact_table│ │ build_dims   │ │ build_wide_table │
└────────┬────────┘ └──────┬───────┘ └────────┬─────────┘
│ │ │
▼ ▼ ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ fact_daily      │ │ dim_customer │ │ wide_daily_user  │
│ events          │ │ dim_event_   │ │ events           │
│ (partitioned)   │ │ type         │ │ (partitioned)    │
└─────────────────┘ └──────────────┘ └──────────────────┘
```


**Key branch descriptions**:

- **Bad data flow (red path)**: During the `validation` stage, if a record is missing required fields, has a type mismatch, or contains extra fields, it is quarantined to `errors/bad_schema/` with an `error_reason` column attached. The pipeline **continues processing** the remaining valid data without interruption.
- **Type change flow**: Type/format violations (non-numeric `amount`,
  timestamp parse failures) are **quarantined at the `validation` stage**
  together with schema violations; they do not reach Silver. The
  validator's `error_reason` distinguishes them
  (`error_type=type_coercion_failed`, see §3.4). A separate "flag and pass
  to Silver" yellow path was considered in the design but is not enabled:
  the single-machine demo chooses fail-safe isolation over carrying
  suspect rows downstream.
- **Deduplication flow**: For duplicate `event_id` values, only the record with the latest `ingestion_timestamp` is kept; the rest are written to `duplicates.log` (including original values and duplicate timestamps) for post-hoc review.

---

## 3. Data Structure Definitions (Precise Schema)

### 3.1 Bronze Layer (Raw JSON-Lines Schema)

**Storage**: one `events.json` per partition — JSON Lines, one raw event per
line, archived **as ingested**: no cleaning, no quality judgement. Values
keep their JSON types (pandas round-trips a JSON integer like `10` as
`10.0`), and rows that are later quarantined at the Silver gate are still
present here (Bronze is the factual landing zone for replay and
audit).

**Partition keys**: `source_system` (top-level directory) + `dt` (ingestion
date derived from `ingestion_timestamp`) — see the layout in §1.

| Field name            | Type   | Description                              | Constraint/Notes                                      |
| :---                  | :---   | :---                                     | :---                                                  |
| `event_id`            | string | Unique event ID                          | UUID v4 format                                        |
| `source_system`       | string | Source system (**partition key**)        | Any raw value — no enum check at this layer           |
| `customer_id`         | string | Customer ID                              | —                                                     |
| `event_type`          | string | Event type                               | —                                                     |
| `event_timestamp`     | string | Event occurrence time (ISO-8601, raw)    | Kept as the original string                           |
| `amount`              | number | Amount (original)                        | May be invalid (e.g. negative) — not yet validated    |
| `currency`            | string | Currency code (original)                 | May be invalid (e.g. `XXX`) — not yet normalized      |
| `ingestion_timestamp` | string | Ingestion time (ISO-8601, raw)           | Source of the `dt` partition key                      |

> Values are stored **as ingested**; the `dt` partition is derived from the
> first 10 characters of `ingestion_timestamp`. Contrast with the Iceberg
> production shape in §6.1.

---

### 3.2 Silver Layer (Cleaned Parquet Schema)

**Partition key**: `event_date` (the date extracted from `event_timestamp`, typed as `date`)

| Field name            | Type                  | Description                                       | Constraint/Notes                                              |
| :---                  | :---                  | :---                                              | :---                                                          |
| `event_id`            | `string`              | Unique event ID                                   | Non-null, UUID v4 format                                      |
| `source_system`       | `string`              | Source system                                     | Enum: `web` / `mobile` / `api`                                |
| `customer_id`         | `string`              | Customer ID                                       | Non-null; may be hash-masked by policy in production          |
| `event_type`          | `string`              | Event type                                        | Non-null, length ≤ 64                                         |
| `event_timestamp`     | `timestamp(us, UTC)`  | Event occurrence time                             | Microsecond precision, UTC timezone                           |
| `amount`              | `double`              | Amount                                            | ≥ 0, original value preserved; `NaN` if conversion fails      |
| `currency`            | `string`              | Currency code                                     | ISO 4217 three-letter code; invalid values corrected to `USD` |
| `ingestion_timestamp` | `timestamp(us, UTC)`  | Ingestion time (from source system or processing) | Must be ≤ current time                                        |
| `event_date`          | `date`                | **Partition column**                              | Derived from `event_timestamp`                                |
| `_raw_json`           | `string`              | Full original record as JSON (audit)               | Added by `reader.read_input`; carried for row-level replay        |
| `_raw_event_timestamp`| `string`              | Original raw `event_timestamp` string              | Backed up by the validator before parse; never overwritten        |
| `_raw_ingestion_timestamp`| `string`           | Original raw `ingestion_timestamp` string          | Backed up by the validator before parse; never overwritten        |
| `_raw_amount`         | `string`              | Backup of the original amount value                | Written by the cleaner on every row (pre-coercion value)          |
| `_is_invalid_currency`| `boolean`             | Whether currency was corrected                    | `true` means original value was invalid, changed to `USD`     |
| `_validation_status`  | `string`              | Validation status                                 | `'passed'` or `'type_mismatch'`                               |
| `_processed_timestamp`| `timestamp(us, UTC)`  | Pipeline processing time                          | Automatically added at write time                             |

---

### 3.3 Gold Layer Structure (Star Schema)

#### Fact table: `fact_daily_events`
| Field name     | Type     | Description                                  |
| :---           | :---     | :---                                         |
| `event_date`   | `date`   | Partition column                             |
| `customer_id`  | `string` | Links to dimension table `dim_customer`      |
| `event_type`   | `string` | Links to dimension table `dim_event_type`    |
| `event_count`  | `bigint` | Total event count for the group              |
| `total_amount` | `double` | Total amount for the group                   |
| `avg_amount`   | `double` | Average amount for the group                 |

#### Dimension table: `dim_customer`
| Field name        | Type     | Description                                                       |
| :---              | :---     | :---                                                              |
| `customer_id`     | `string` | Primary key, unique                                               |
| `first_seen_date` | `date`   | (Reserved) first-seen date; currently set to the min `event_date` |

#### Dimension table: `dim_event_type`
| Field name    | Type     | Description                                        |
| :---          | :---     | :---                                               |
| `event_type`  | `string` | Primary key, unique                                |
| `category`    | `string` | (Reserved) business category; currently blank      |

#### Wide table (denormalized): `wide_daily_user_events`
Left-joins `fact_daily_events` with `dim_customer` and `dim_event_type`, containing all fact and dimension fields, directly available for BI queries, avoiding runtime joins.

---

### 3.4 Error Record Schema (`errors/` directory)

Each error file uses **JSON Lines** format, one error object per line, containing the following fields:

| Field name            | Type              | Description                                                                        |
| :---                  | :---              | :---                                                                               |
| `original_json`       | `string`          | JSON rebuild of the offending row (pandas round-trip; keys missing from the raw line render as `null` — see Bronze §3.1 "as ingested" note) |
| `error_type`          | `string`          | Error type: `schema_mismatch` / `type_coercion_failed`                             |
| `error_details`       | `string`          | Specific reason, e.g. `"field 'event_id' missing"` or `"amount cannot be parsed as number"` |
| `ingestion_timestamp` | `string` (ISO8601)| The time the pipeline processed this record                                       |

---

## 4. Data Freshness and Reprocessing Mechanism

- **Batch window**: The pipeline is designed to run once daily, processing the previous day's (UTC) `event_timestamp` data by default. A specific historical date can be specified via the `--event-date YYYY-MM-DD` CLI argument for flexible backfill.
- **Idempotency guarantee**: Silver and Gold layer writes use **partition overwrite** mode (`mode='overwrite'`). Re-running the same date fully overwrites that partition, ensuring consistent results without duplicate data.
- **Late data strategy**: If a record's `event_timestamp` belongs to a past date (e.g. data arriving 3 days late), the pipeline writes it to the corresponding historical partition without discarding it. This behavior relies on the partition overwrite mechanism, and the Bronze layer retains the original JSON for replay at any time.
- **Safe backfill**: By specifying `--event-date`, only the data for a specific date is reprocessed without affecting other partitions, enabling precise remediation.

---

## 5. Lineage and Observability (Design Highlights)

- **Lineage tracking**: The path of each record from Bronze (raw JSON) to Silver (Parquet) to Gold (aggregation table) is traceable via `_processed_timestamp` and partition keys. OpenLineage can be integrated in the future for finer-grained field-level lineage.
- **Run metrics**: At the end of each run a `metrics.json` file (location
  from the `metrics.output_file` config) is output with total input rows,
  bronze rows, validation pass/fail counts, duplicates removed, and
  Silver/Gold row counts plus start/end times. Per-stage durations are not
  yet collected.
- **Data freshness monitoring**: In the orchestration layer (e.g. Airflow), a sensor can be configured to check whether the latest Silver partition's `event_date` matches the current date; if the delay exceeds a threshold, an alert is triggered.

---

## 6. Production Table Format Reference — Apache Iceberg (SQL Assets)

The Bronze/Silver/Gold layouts in §1 are **directory + file** layouts — what
the single-machine demo writes today. In the target big-data environment
(see `docs/architecture.md` §5) the same layers are managed as **Iceberg
tables**: the data files remain Parquet, but a catalog + metadata layer adds
ACID transactions, partition evolution, snapshot isolation, and time travel.

The SQL below is prepared as a **production asset**. It is not executable in
this repository's current environment (it requires Spark + the Iceberg
runtime + a catalog); it documents the target shape and is ready to run once
a big-data environment is available. Dialect: Spark SQL + Iceberg.

### 6.1 Bronze — raw archive (append-only, immutable)

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

### 6.2 Silver — cleaned detail (upsert by business key, idempotent refresh)

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
    _validation_status  STRING,  -- 'ok' / 'type_mismatch'
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

### 6.3 Gold — curated star schema (idempotent overwrite per partition)

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

### 6.4 Analytics reads — snapshot isolation and time travel

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

### 6.5 Mapping to the demo implementation

| Demo (this repo, Pandas)              | Production equivalent (Iceberg/Spark)              |
| :------------------------------------ | :------------------------------------------------- |
| `data/bronze/{source}/dt=.../events.json` | `bronze.events` table, append-only, 30-day retention |
| `data/silver/event_date=.../data.parquet` | `silver.events` table, `DELETE+INSERT` / `MERGE INTO` |
| `data/gold/fact_daily_events/...`     | `gold.fact_daily_events` table, `INSERT OVERWRITE`  |
| partition-overwrite (idempotency)     | Iceberg transactions + snapshot isolation           |
| `_raw_json` audit column              | full Bronze replay via snapshot/time travel         |

