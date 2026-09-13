# Table Contract: wide_daily_user_events
## Layer

Gold (curated)

## Grain

Same as `fact_daily_events`: one row per `event_date` plus `customer_id` plus `event_type` group, denormalized with dimension columns.

## Business Primary Key

Composite: (`event_date`, `customer_id`, `event_type`)

## Deduplication

Not applicable. Built by left-joining the fact table with dimension tables. Source-level deduplication happens in Silver.

## Partition

`event_date` (date). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.

## Field List

| Field | Type | Description | Source |
|---|---|---|---|
| `event_date` | date | Partition column | fact table |
| `customer_id` | string | Customer ID | fact table |
| `event_type` | string | Event type | fact table |
| `event_count` | bigint | Total event count | fact table |
| `total_amount` | double | Total amount | fact table |
| `avg_amount` | double | Average amount | fact table |
| `first_seen_date` | date | First seen date for the customer | dim_customer (left join on `customer_id`) |
| `category` | string | Reserved business category (currently blank) | dim_event_type (left join on `event_type`) |

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent).
- **Source**: built from the fact table and dimension tables. The fact table is always built from the full on-disk Silver snapshot.
- **Retention**: no retention policy. All partitions persist until manually cleaned.
- **Join semantics**: left join with `validate="many_to_one"` to ensure each fact row maps to at most one dimension row. A dimension miss produces `NaN` in the dimension columns, not a dropped row.
