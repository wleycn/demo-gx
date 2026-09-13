# Table Contract: dim_event_type

## Layer

Gold (curated)

## Grain

One row per unique `event_type`.

## Business Primary Key

`event_type`

## Deduplication

Built via `drop_duplicates()` on `event_type` from the Silver snapshot.

## Partition

None. Full snapshot, non-partitioned. Written as a single `data.parquet` file.

## Field List

| Field | Type | Description |
|---|---|---|
| `event_type` | string | Primary key, unique |
| `category` | string | Reserved for business category; currently blank |

## Lifecycle

- **Write mode**: full overwrite. The entire table is rewritten on every run.
- **Source**: built from the full on-disk Silver snapshot. Rule: DATA-DESIGN.md section 2.4.
- **Retention**: no retention policy. The table is overwritten on each run.
- **Future extension**: the `category` field is reserved for a business classification but is currently not populated.
