# Table Contract: quarantine

## Layer

Errors (quarantine)

## Subject

Schema-validation failures. One row per rejected input record, carrying the
original JSON and the reason it was quarantined.

## Grain

One row per rejected record per run.

## Business Primary Key

Not applicable. The same record reappears on a rerun, and one record can be
rejected for more than one reason, so there is no natural key. The table is
partition-overwritten: a rerun replaces the rows of one event date.

## Deduplication

None. The quarantined rows are the output of the validator, not an input to
further processing.

## Partition

`event_date` (string, derived from `event_timestamp`). Partition directory
format: `event_date={YYYY-MM-DD|unknown}/data.parquet`.

- **Rationale**: a scoped backfill replaces one day and leaves the others
  alone. The partition key is the record's own event date, not the run date.
- **Unparseable timestamps**: a record whose `event_timestamp` does not parse
  goes to `event_date=unknown`. It is never dropped.
- **Type**: `event_date` is a string here, not a date. The table has to be able to
  say `unknown`, and the value matches the partition directory name. The other
  tables carry a real date because every row in them has one.
- **Write mode**: partition-scoped overwrite (idempotent). Each partition's
  `data.parquet` is rewritten per run.
- **Estimated volume**: 0 to 10 rows per partition in the demo sample.

## Field List

| Field | Type | Description | Constraint |
|---|---|---|---|
| `original_json` | string | JSON rebuild of the offending row | Pandas round-trip; keys missing from the raw line render as `null` |
| `error_type` | string | `schema_mismatch` or `type_coercion_failed` | Derived from the validator's per-rule error reason |
| `error_details` | string | Specific reason text from the validator | e.g. "field 'event_id' missing", "amount not numeric" |
| `ingestion_timestamp` | string (ISO-8601) | The UTC time the pipeline processed this record | Stamped by the run timestamp |
| `event_date` | string | Partition column | `YYYY-MM-DD` or `unknown` |

## Quality Rules

1. Every rejected record is present, including rows whose type conversion
   failed. They are filed with `error_type=type_coercion_failed`.
2. `error_type` is `type_coercion_failed` when the reason contains "not
   numeric", "not string", or "parse failed". All other reasons are
   `schema_mismatch`.
3. A record with an unparseable `event_timestamp` goes to `event_date=unknown`
   and is never dropped.
4. The table is partition-overwritten. A rerun of the same batch leaves the
   content byte-for-byte unchanged.

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent).
- **Retention**: no retention policy. All partitions persist until manually
  cleaned.
- **Reprocessing**: `--event-date` reprocesses one date. Late data writes to
  the corresponding historical partition.

## Dependencies

- **Upstream**: `SchemaValidator.validate` returns the invalid frame that
  feeds the envelope.
- **Downstream**: none. The quarantine table is for audit and replay only.
