# Table Contract: fact_daily_events
## Layer

Gold (curated)

## Grain

One row per `event_date` plus `customer_id` plus `event_type` group.

## Business Primary Key

Composite: (`event_date`, `customer_id`, `event_type`)

## Deduplication

Not applicable. The fact table is an aggregation built from Silver detail data. Source-level deduplication happens in Silver by `event_id`.

## Partition

`event_date` (date). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.

## Field List

| Field | Type | Description |
|---|---|---|
| `event_date` | date | Partition column |
| `customer_id` | string | Links to `dim_customer` |
| `event_type` | string | Links to `dim_event_type` |
| `event_count` | bigint | Total event count for the group |
| `total_amount` | double | Total amount for the group |
| `avg_amount` | double | Average amount for the group |

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent).
- **Source**: always built from the full on-disk Silver snapshot, never from the in-memory batch. This ensures a backfill run for one date does not lose rows or shrink dimensions.
- **Retention**: no retention policy. All partitions persist until manually cleaned.
- **Reprocessing**: `--event-date` reprocesses one date. Gold is always rebuilt from the full Silver snapshot.
