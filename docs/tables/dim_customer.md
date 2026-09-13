# Table Contract: dim_customer

## Layer

Gold (curated)

## Grain

One row per unique `customer_id`.

## Business Primary Key

`customer_id`

## Deduplication

Built via `drop_duplicates()` on `customer_id` from the Silver snapshot.

## Partition

None. Full snapshot, non-partitioned. Written as a single `data.parquet` file.

## Field List

| Field | Type | Description |
|---|---|---|
| `customer_id` | string | Primary key, unique |
| `first_seen_date` | date | Minimum `event_date` for this customer across the Silver snapshot |

## Lifecycle

- **Write mode**: full overwrite. The entire table is rewritten on every run.
- **Source**: built from the full on-disk Silver snapshot, so a backfill run cannot lose customers or reset `first_seen_date`. Rule: DATA-DESIGN.md section 2.4.
- **Retention**: no retention policy. The table is overwritten on each run.
- **Future extension**: the `category` field is reserved for a business classification but is currently not populated.
