# Table Contract: dim_customer

## Layer

Gold (curated)

## Subject

Customer. One row per customer that appears anywhere in the Silver snapshot.

## Grain

One row per unique `customer_id`.

## Business Primary Key

`customer_id`

## Deduplication

Built via `drop_duplicates()` on `customer_id` from the Silver snapshot.

## Partition

None. Full snapshot, non-partitioned. Written as a single `data.parquet` file.

- **Rationale**: the table is a full snapshot with a small row count, so partitions would add directories without narrowing any read.
- **Estimated volume**: 44 rows in the demo sample. The table stays small because it holds one row per customer.

## Field List

| Field | Type | Description |
|---|---|---|
| `customer_id` | string | Primary key, unique |
| `first_seen_date` | date | Minimum `event_date` for this customer across the Silver snapshot |

## Monetary Convention

Not applicable. This table carries no monetary field.

## PII and Masking

- **Direct identifier**: `customer_id`. This table exists to list those identifiers, so the whole table is sensitive.
- **Masking today**: none in this demo. Production masking belongs at the Bronze entry boundary.
- **Cross-reference**: the full statement lives in [silver_events.md](silver_events.md) under "PII and Masking".

## Lifecycle

- **Write mode**: full overwrite. The entire table is rewritten on every run.
- **Source**: built from the full on-disk Silver snapshot, so a backfill run cannot lose
  customers or reset `first_seen_date`. Rule: DATA-DESIGN.md section 2.4.
- **Retention**: no retention policy. The table is overwritten on each run.
- **Compaction and snapshot retention**: not implemented. See KNOWN-ISSUE.md `#no-snapshot-lifecycle`.

## Freshness SLA and Owner

- **Freshness SLA**: none. The demo runs on demand, with no schedule and no alert wired.
- **Owner**: the repository maintainers.
- **Production rule**: SLA and alerting belong in the orchestration layer. See DATA-DESIGN.md section 3.

## Dependencies

- **Upstream**: `silver_events`, read as the full on-disk snapshot.
- **Downstream**: `wide_daily_user_events`, which left-joins this table on `customer_id`.

## Quality Rules

1. `customer_id` is unique and non-null.
2. `first_seen_date` equals the minimum `event_date` for that customer over the full Silver snapshot.
3. The row count is stable under a single-day backfill, because the build reads the full snapshot.
4. Every `customer_id` in `fact_daily_events` has a matching row here, so the wide-table join never misses.
