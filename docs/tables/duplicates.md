# Table Contract: duplicates

## Layer

Errors (superseded duplicates)

## Subject

Duplicate event rows that were superseded by a newer ingestion. One row per
superseded duplicate, carrying the full Silver-shaped frame the deduplicator
returned.

## Grain

One row per superseded duplicate per run.

## Business Primary Key

Not applicable. The same duplicate reappears across reruns. The table is
partition-overwritten, so a rerun replaces the rows for one event date rather
than appending.

## Deduplication

None. The rows in this table are the output of the Silver deduplicator, not an
input to further processing. The deduplication rule itself lives in
[silver_events.md](silver_events.md).

## Partition

`event_date` (date, derived from `event_timestamp`). Partition directory
format: `event_date={YYYY-MM-DD}/data.parquet`.

- **Rationale**: a scoped backfill replaces one day and leaves the others
  alone. The partition key matches Silver's.
- **Write mode**: partition-scoped overwrite (idempotent). Each partition's
  `data.parquet` is rewritten through a temporary file and then moved into place.
- **Scope clearing**: a run also drops the covered days that hold nothing, and the table
  directory itself once no partition is left. An absent table therefore means zero rows.
- **Estimated volume**: 0 to 2 rows per partition in the demo sample.

## Field List

The frame `Deduplicator.deduplicate` returns. It carries every column the
cleaner stage produced, including `event_date`. No columns are invented or
dropped.

| Field | Type | Description | Constraint |
|---|---|---|---|
| `event_id` | string | Unique event ID | UUID v4 format |
| `source_system` | string | Source system | Enum: `web`, `mobile`, `api` |
| `customer_id` | string | Customer ID | Masked at the ingestion boundary |
| `event_type` | string | Event type | Non-null, length at most 64 |
| `event_timestamp` | timestamp (us, UTC) | Event occurrence time | Microsecond precision, UTC timezone |
| `amount` | double | Amount | At least 0 |
| `currency` | string | Currency code | ISO 4217 three-letter code |
| `ingestion_timestamp` | timestamp (us, UTC) | Ingestion time from source system | Must be at most current time |
| `_raw_json` | string | Full original record as JSON | Added by `reader.read_input` |
| `_raw_event_timestamp` | string | Original raw `event_timestamp` string | Backed up by the validator |
| `_raw_ingestion_timestamp` | string | Original raw `ingestion_timestamp` string | Backed up by the validator |
| `_is_invalid_currency` | boolean | Whether currency was corrected | `true` means original value was invalid |
| `_raw_amount` | double | Backup of amount after numeric coercion | Written by the cleaner |
| `event_date` | date | Partition column | Derived from `event_timestamp` |

## Quality Rules

1. The frame is the exact output of `Deduplicator.deduplicate`. No columns
   are invented or dropped.
2. Every row is a superseded duplicate: its `event_id` appears in a row with
   a later `ingestion_timestamp` in the same batch.
3. The table is partition-overwritten. A rerun of the same batch leaves the
   content byte-for-byte unchanged.

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent).
- **Retention**: no retention policy beyond scope clearing: a partition stays until a
  run covers that day again or someone cleans it manually.
- **Reprocessing**: `--event-date` reprocesses one date.

## Dependencies

- **Upstream**: `Deduplicator.deduplicate` returns the duplicates frame.
- **Downstream**: none. The duplicates table is for audit only.
