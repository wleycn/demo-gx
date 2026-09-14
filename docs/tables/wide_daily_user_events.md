# Table Contract: wide_daily_user_events

## Layer

Gold (curated)

## Subject

Events. The daily fact plus dimension columns in one flat table, for BI tools that avoid joins.

## Grain

Same as `fact_daily_events`: one row per `event_date` plus `customer_id` plus `event_type`
group, denormalized with dimension columns.

## Business Primary Key

Composite: (`event_date`, `customer_id`, `event_type`)

## Deduplication

Not applicable. Built by left-joining the fact table with dimension tables. Source-level
deduplication happens in Silver.

## Partition

`event_date` (date). Partition directory format: `event_date={YYYY-MM-DD}/data.parquet`.

- **Rationale**: the partition mirrors the fact table, so the two stay aligned per day.
- **Estimated volume**: 1 to 7 rows per partition in the demo sample, matching the fact table.

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

## Monetary Convention

- `total_amount` and `avg_amount` are copied from `fact_daily_events`, so they follow the same convention: a decimal in the currency's major unit, never converted.
- **Known limitation**: the same currency caveat applies. The table has no currency column, so a mixed-currency group sums without conversion.

## PII and Masking

- **Direct identifier**: `customer_id`, carried through from the fact table.
- **Masking today**: none in this demo. Production masking belongs at the Bronze entry boundary.
- **Cross-reference**: the full statement lives in [silver_events.md](silver_events.md) under "PII and Masking".

## Lifecycle

- **Write mode**: partition-scoped overwrite (idempotent).
- **Source**: built from the fact table and dimension tables; the fact table in turn reads
  the full on-disk Silver snapshot. Rule: DATA-DESIGN.md section 2.4.
- **Retention**: no retention policy. All partitions persist until manually cleaned.
- **Join semantics**: left join with `validate="many_to_one"` to ensure each fact row maps
  to at most one dimension row. A dimension miss produces `NaN` in the dimension columns,
  not a dropped row.
- **Compaction and snapshot retention**: not implemented. See KNOWN-ISSUE.md `#no-snapshot-lifecycle`.

## Freshness SLA and Owner

- **Freshness SLA**: none. The demo runs on demand, with no schedule and no alert wired.
- **Owner**: the repository maintainers.
- **Production rule**: SLA and alerting belong in the orchestration layer. See DATA-DESIGN.md section 3.

## Dependencies

- **Upstream**: `fact_daily_events`, `dim_customer`, and `dim_event_type`.
- **Downstream**: BI and ML consumers. No consumer is wired in this demo.

## Quality Rules

1. The row count equals the fact table row count. A left join never drops a fact row.
2. Both joins are many-to-one, so no fact row fans out into several rows.
3. A dimension miss leaves `NaN` in the dimension columns and still keeps the row.
4. The composite key `event_date`, `customer_id`, `event_type` is unique, inherited from the fact table.
