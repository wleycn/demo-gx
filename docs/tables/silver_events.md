# Table Contract: silver_events
## Layer

Silver (cleaned detail)

## Grain

One row per unique event (after deduplication by `event_id`).

## Business Primary Key

`event_id` (UUID v4)

## Deduplication

By `event_id`, keeping the record with the latest `ingestion_timestamp`. On an exact tie (identical `ingestion_timestamp`), the last-occurring row in the input file wins (keep-last; stable sort). Superseded duplicates are written to `errors/duplicates.log`.

## Partition

`event_date` (date, derived from `event_timestamp`). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.

## Field List

| Field | Type | Description | Constraint |
|---|---|---|---|
| `event_id` | string | Unique event ID | Non-null, UUID v4 format |
| `source_system` | string | Source system | Enum: `web`, `mobile`, `api` |
| `customer_id` | string | Customer ID | Non-null; may be hash-masked by policy in production |
| `event_type` | string | Event type | Non-null, length at most 64 |
| `event_timestamp` | timestamp (us, UTC) | Event occurrence time | Microsecond precision, UTC timezone |
| `amount` | double | Amount | At least 0, original value preserved; `NaN` if conversion fails |
| `currency` | string | Currency code | ISO 4217 three-letter code; invalid values corrected to `USD` |
| `ingestion_timestamp` | timestamp (us, UTC) | Ingestion time from source system | Must be at most current time |
| `event_date` | date | Partition column | Derived from `event_timestamp` |
| `_raw_json` | string | Full original record as JSON | Added by `reader.read_input`; for row-level replay |
| `_raw_event_timestamp` | string | Original raw `event_timestamp` string | Backed up by the validator before parse; never overwritten |
| `_raw_ingestion_timestamp` | string | Original raw `ingestion_timestamp` string | Backed up by the validator before parse; never overwritten |
| `_raw_amount` | double | Backup of amount after validator's numeric coercion | Written by the cleaner on every row |
| `_is_invalid_currency` | boolean | Whether currency was corrected | `true` means original value was invalid, changed to `USD` |
| `_validation_status` | string | Validation status | Always `passed` in the current implementation (`type_mismatch` is a reserved value) |
| `_processed_timestamp` | timestamp (us, UTC) | Pipeline processing time | Added at write time |

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent). Each partition's `data.parquet` is rewritten per run.
- **Empty partitions**: not pruned. A full clean re-run (`make clean`) removes all artifacts.
- **Retention**: no retention policy. All partitions persist until manually cleaned.
- **Reprocessing**: `--event-date` reprocesses one date. Late data writes to the corresponding historical partition.
