# Table Contract: fact_daily_events

## Layer

Gold (curated)

## Subject

Events. Daily aggregates by customer and event type, for BI and ML use.

## Grain

One row per `event_date` plus `customer_id` plus `event_type` group.

## Business Primary Key

Composite: (`event_date`, `customer_id`, `event_type`)

## Deduplication

Not applicable. The fact table is an aggregation built from Silver detail data. Source-level
deduplication happens in Silver by `event_id`.

## Partition

`event_date` (date). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.

- **Rationale**: the partition mirrors Silver, so a single-day backfill rewrites one Gold partition.
- **Estimated volume**: single-digit rows per partition in the demo sample, one row per (event date, customer, event type) group. Exact counts are read from `make check-data`.

## Field List

| Field | Type | Description |
|---|---|---|
| `event_date` | date | Partition column |
| `customer_id` | string | Links to `dim_customer` |
| `event_type` | string | Links to `dim_event_type` |
| `event_count` | bigint | Total event count for the group |
| `total_amount` | double | Total amount for the group |
| `avg_amount` | double | Average amount for the group |

## Monetary Convention

- `total_amount` and `avg_amount` follow the Silver amount convention: a decimal in the currency's major unit, never converted. See [silver_events.md](silver_events.md).
- **Known limitation**: this table has no currency column. A group that mixes currencies sums them without conversion, so `total_amount` is only meaningful for a single-currency group.

## PII and Masking

- **Direct identifier**: `customer_id`, inherited from Silver.
- **Masking today**: none in this demo. Production masking belongs at the Bronze entry boundary.
- **Cross-reference**: the full statement lives in [silver_events.md](silver_events.md) under "PII and Masking".

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent).
- **Source**: built from the full on-disk Silver snapshot, so a backfill run cannot lose
  rows or shrink dimensions. Rule: DATA-DESIGN.md section 2.4.
- **Retention**: no retention policy. All partitions persist until manually cleaned.
- **Reprocessing**: `--event-date` reprocesses one date. Gold rebuild semantics:
  DATA-DESIGN.md section 2.6.
- **Compaction and snapshot retention**: not implemented. See KNOWN-ISSUE.md `#no-snapshot-lifecycle`.

## Freshness SLA and Owner

- **Freshness SLA**: none. The demo runs on demand, with no schedule and no alert wired.
- **Owner**: the repository maintainers.
- **Production rule**: SLA and alerting belong in the orchestration layer. See DATA-DESIGN.md section 3.

## Dependencies

- **Upstream**: `silver_events`, read as the full on-disk snapshot.
- **Downstream**: `wide_daily_user_events`, which left-joins this table with both dimensions.

## Quality Rules

1. The composite key `event_date`, `customer_id`, `event_type` is unique.
2. `event_count` equals the number of Silver rows in the group and is at least 1.
3. `total_amount` equals the sum of `amount` over the group.
4. `avg_amount` equals the mean of `amount` over the group.
5. A group never mixes rows from different `event_date` values.
6. A dimension miss does not drop a row. The fact table builds straight from Silver.
