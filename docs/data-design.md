# Data Flow and Data Structure Design

## 1. Physical Data Paths (Storage Layout)

Adopts an **environment-isolated** directory structure. Local development uses `./data` as the root directory; production can map to S3/ADLS (via configuration switching).
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
├── type_mismatch/ # Type conversion failures (with _raw columns)
│ └── {timestamp}_errors.json
└── duplicates.log # Deduplication record log (plain text, appended)


---

## 2. Detailed Data Flow (with Exception Branches)

The diagram below shows the complete path from input to output, including the handling flow for bad data and special cases.
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


**Key branch descriptions**:

- **Bad data flow (red path)**: During the `validation` stage, if a record is missing required fields, has a type mismatch, or contains extra fields, it is quarantined to `errors/bad_schema/` with an `error_reason` column attached. The pipeline **continues processing** the remaining valid data without interruption.
- **Type change flow (yellow path)**: During the `clean` stage, if a numeric field such as `amount` cannot be converted to a number, the original value is preserved in the `_raw_amount` column and `_validation_status` is set to `'type_mismatch'`. Such records still enter Silver and trigger a log alert.
- **Deduplication flow**: For duplicate `event_id` values, only the record with the latest `ingestion_timestamp` is kept; the rest are written to `duplicates.log` (including original values and duplicate timestamps) for post-hoc review.

---

## 3. Data Structure Definitions (Precise Schema)

### 3.1 Silver Layer (Cleaned Parquet Schema)

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
| `_raw_amount`         | `string`              | (Optional) original amount string                 | Populated only when amount type conversion fails              |
| `_is_invalid_currency`| `boolean`             | Whether currency was corrected                    | `true` means original value was invalid, changed to `USD`     |
| `_validation_status`  | `string`              | Validation status                                 | `'passed'` or `'type_mismatch'`                               |
| `_processed_timestamp`| `timestamp(us, UTC)`  | Pipeline processing time                          | Automatically added at write time                             |

---

### 3.2 Gold Layer Structure (Star Schema)

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

### 3.3 Error Record Schema (`errors/` directory)

Each error file uses **JSON Lines** format, one error object per line, containing the following fields:

| Field name            | Type              | Description                                                                        |
| :---                  | :---              | :---                                                                               |
| `original_json`       | `string`          | The complete JSON string of the original input line                                |
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
- **Run metrics**: At the end of each run, `logs/metrics_{timestamp}.json` is output with total input rows, validation pass count, validation fail count, deduplication removal count, and per-stage durations, for monitoring and SLA evaluation.
- **Data freshness monitoring**: In the orchestration layer (e.g. Airflow), a sensor can be configured to check whether the latest Silver partition's `event_date` matches the current date; if the delay exceeds a threshold, an alert is triggered.

---
