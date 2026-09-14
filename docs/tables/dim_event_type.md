# Table Contract: dim_event_type

## Layer

Gold (curated)

## Subject

Event type. Reference list of every event type seen in the Silver snapshot.

## Grain

One row per unique `event_type`.

## Business Primary Key

`event_type`

## Deduplication

Built via `drop_duplicates()` on `event_type` from the Silver snapshot.

## Partition

None. Full snapshot, non-partitioned. Written as a single `data.parquet` file.

- **Rationale**: the table is a small reference list, so partitions would add directories without narrowing any read.
- **Estimated volume**: 5 rows in the demo sample. The count tracks the number of distinct event types.

## Field List

| Field | Type | Description |
|---|---|---|
| `event_type` | string | Primary key, unique |

## Monetary Convention

Not applicable. This table carries no monetary field.

## PII and Masking

Not applicable. An event type is a label, not a person, so the table holds no personal data.

## Lifecycle

- **Write mode**: full overwrite. The entire table is rewritten on every run.
- **Source**: built from the full on-disk Silver snapshot. Rule: DATA-DESIGN.md section 2.4.
- **Retention**: no retention policy. The table is overwritten on each run.
- **Future extension**: the `category` field is reserved for a business classification but
  is currently not populated.
- **Compaction and snapshot retention**: not implemented. See KNOWN-ISSUE.md `#no-snapshot-lifecycle`.

## Freshness SLA and Owner

- **Freshness SLA**: none. The demo runs on demand, with no schedule and no alert wired.
- **Owner**: the repository maintainers.
- **Production rule**: SLA and alerting belong in the orchestration layer. See DATA-DESIGN.md section 3.

## Dependencies

- **Upstream**: `silver_events`, read as the full on-disk snapshot.
- **Downstream**: `wide_daily_user_events`, which left-joins this table on `event_type`.

## Quality Rules

1. `event_type` is unique and non-null.
2. The list is rebuilt from the full Silver snapshot, so a backfill never removes a type.
3. Every `event_type` in `fact_daily_events` has a matching row here, so the wide-table join never misses.
